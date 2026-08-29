"""Turns one execution-stream event into a finished Execution row.

Idempotent against redelivery: skips the job unless status is still QUEUED.
"""

import asyncio
import time
import uuid
from datetime import UTC, datetime

import docker
import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import WorkerSettings
from db import session_scope
from metrics import execution_duration_seconds, execution_failure_total, execution_success_total
from models import AuditEventType, AuditLog, Execution, ExecutionLog, ExecutionStatus, File
from pubsub import publish_status_update
from runtimes.registry import UnsupportedLanguageError, get_runtime
from sandbox.docker_runner import DockerSandboxRunner, SandboxResult

logger = structlog.get_logger(__name__)

_STATUS_FROM_SANDBOX = {
    "success": ExecutionStatus.SUCCESS,
    "failed": ExecutionStatus.FAILED,
    "timeout": ExecutionStatus.TIMEOUT,
}

# Absorbs a rare visibility race between the API's commit and this worker's
# read on a different connection.
_NOT_FOUND_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.2)


class ExecutionManager:
    def __init__(self, settings: WorkerSettings, docker_client: docker.DockerClient, redis: Redis):
        self.settings = settings
        self.sandbox = DockerSandboxRunner(docker_client)
        self.redis = redis

    async def handle_event(self, fields: dict[str, str]) -> None:
        execution_id = uuid.UUID(fields["execution_id"])

        language, code = await self._claim_and_start(execution_id)
        if language is None or code is None:
            return

        started = time.monotonic()
        try:
            runtime = get_runtime(language, self.settings)
        except UnsupportedLanguageError as exc:
            await self._mark_failed_precondition(execution_id, str(exc))
            return

        # Runs outside any DB transaction — no reason to hold a connection
        # open for the duration of a subprocess we don't control.
        result = await asyncio.to_thread(self.sandbox.run, runtime, code)
        wall_ms = int((time.monotonic() - started) * 1000)

        await self._complete(execution_id, result, wall_ms)

    async def _claim_and_start(self, execution_id: uuid.UUID) -> tuple[str | None, str | None]:
        if not await self._exists_with_retry(execution_id):
            logger.warning("execution_not_found", execution_id=str(execution_id))
            return None, None

        async with session_scope() as session:
            execution = await session.get(Execution, execution_id)
            if execution is None:
                logger.warning("execution_not_found", execution_id=str(execution_id))
                return None, None
            if execution.status != ExecutionStatus.QUEUED:
                logger.info(
                    "execution_skipped_not_queued",
                    execution_id=str(execution_id),
                    status=execution.status.value,
                )
                return None, None

            file = await session.scalar(select(File).where(File.id == execution.file_id))
            if file is None or file.content is None:
                await self._fail(session, execution, "The file to execute no longer exists")
                return None, None

            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.now(UTC)
            session.add(
                ExecutionLog(
                    execution_id=execution.id,
                    from_status=ExecutionStatus.QUEUED.value,
                    to_status=ExecutionStatus.RUNNING.value,
                )
            )
            session.add(
                AuditLog(
                    user_id=execution.user_id,
                    event_type=AuditEventType.EXECUTION_STARTED,
                    resource_type="execution",
                    resource_id=execution.id,
                )
            )
            await session.commit()
            logger.info(
                "execution_started", execution_id=str(execution_id), language=execution.language
            )

        await publish_status_update(self.redis, execution_id, ExecutionStatus.RUNNING.value)
        return execution.language, file.content

    @staticmethod
    async def _exists_with_retry(execution_id: uuid.UUID) -> bool:
        async with session_scope() as session:
            if await session.get(Execution, execution_id) is not None:
                return True

        for delay in _NOT_FOUND_RETRY_DELAYS_SECONDS:
            await asyncio.sleep(delay)
            async with session_scope() as session:
                if await session.get(Execution, execution_id) is not None:
                    return True
        return False

    async def _mark_failed_precondition(self, execution_id: uuid.UUID, message: str) -> None:
        async with session_scope() as session:
            execution = await session.get(Execution, execution_id)
            if execution is not None and execution.status == ExecutionStatus.RUNNING:
                await self._fail(session, execution, message)

    async def _complete(self, execution_id: uuid.UUID, result: SandboxResult, wall_ms: int) -> None:
        async with session_scope() as session:
            execution = await session.get(Execution, execution_id)
            if execution is None or execution.status != ExecutionStatus.RUNNING:
                return

            new_status = _STATUS_FROM_SANDBOX[result.status]
            session.add(
                ExecutionLog(
                    execution_id=execution.id,
                    from_status=ExecutionStatus.RUNNING.value,
                    to_status=new_status.value,
                )
            )
            execution.status = new_status
            execution.stdout = result.stdout
            execution.stderr = result.stderr
            execution.exit_code = result.exit_code
            execution.duration_ms = result.duration_ms
            execution.completed_at = datetime.now(UTC)
            session.add(
                AuditLog(
                    user_id=execution.user_id,
                    event_type=AuditEventType.EXECUTION_COMPLETED,
                    resource_type="execution",
                    resource_id=execution.id,
                    details={"status": new_status.value, "exit_code": result.exit_code},
                )
            )
            await session.commit()

            logger.info(
                "execution_completed",
                execution_id=str(execution_id),
                status=new_status.value,
                exit_code=result.exit_code,
                duration_ms=result.duration_ms,
                wall_clock_ms=wall_ms,
            )

        if new_status == ExecutionStatus.SUCCESS:
            execution_success_total.inc()
        else:
            execution_failure_total.inc()
        execution_duration_seconds.observe(result.duration_ms / 1000)

        await publish_status_update(self.redis, execution_id, new_status.value)

    async def _fail(self, session: AsyncSession, execution: Execution, message: str) -> None:
        execution_id = execution.id
        session.add(
            ExecutionLog(
                execution_id=execution.id,
                from_status=execution.status.value,
                to_status=ExecutionStatus.FAILED.value,
                message=message,
            )
        )
        execution.status = ExecutionStatus.FAILED
        execution.stderr = message
        execution.completed_at = datetime.now(UTC)
        await session.commit()
        logger.warning(
            "execution_failed_precondition", execution_id=str(execution_id), reason=message
        )
        await publish_status_update(self.redis, execution_id, ExecutionStatus.FAILED.value)
