import hashlib
import uuid

from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.audit_service import record_audit_event
from app.core.metrics import execution_total
from app.domain.enums.audit_event import AuditEventType
from app.domain.enums.execution_status import (
    ExecutionStatus,
    InvalidExecutionTransitionError,
    ensure_transition,
)
from app.domain.enums.file_type import FileType
from app.domain.models.execution import Execution
from app.domain.models.execution_log import ExecutionLog
from app.domain.models.file import File
from app.domain.models.idempotency_key import IdempotencyKey
from app.domain.models.project import Project
from app.infrastructure.redis.streams import publish_execution_job
from app.schemas.envelope import ApiError
from app.schemas.execution import ExecutionStats
from app.schemas.pagination import PageParams


def _request_hash(project_id: uuid.UUID, file_id: uuid.UUID, user_id: uuid.UUID) -> str:
    raw = f"{project_id}:{file_id}:{user_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ExecutionService:
    """Executions are always accessed through their owning project: a user can
    only ever see executions that belong to a project they own."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_owned(self, owner_id: uuid.UUID, execution_id: uuid.UUID) -> Execution:
        execution = await self.db.scalar(
            select(Execution)
            .join(Project, Project.id == Execution.project_id)
            .where(Execution.id == execution_id, Project.owner_id == owner_id)
        )
        if execution is None:
            raise ApiError(
                status_code=404, code="EXECUTION_NOT_FOUND", message="Execution not found"
            )
        return execution

    async def list_for_project(
        self, project_id: uuid.UUID, params: PageParams
    ) -> tuple[list[Execution], int]:
        filters = [Execution.project_id == project_id]

        total = await self.db.scalar(select(func.count()).select_from(Execution).where(*filters))

        result = await self.db.scalars(
            select(Execution)
            .where(*filters)
            .order_by(Execution.created_at.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        return list(result.all()), total or 0

    async def list_for_user(
        self, owner_id: uuid.UUID, params: PageParams
    ) -> tuple[list[tuple[Execution, str]], int]:
        """Executions across every project the user owns, most recent first,
        paired with each execution's project name."""
        filters = [Project.owner_id == owner_id]

        total = await self.db.scalar(
            select(func.count())
            .select_from(Execution)
            .join(Project, Project.id == Execution.project_id)
            .where(*filters)
        )

        result = await self.db.execute(
            select(Execution, Project.name)
            .join(Project, Project.id == Execution.project_id)
            .where(*filters)
            .order_by(Execution.created_at.desc())
            .offset(params.offset)
            .limit(params.page_size)
        )
        pairs = [(row.Execution, row.name) for row in result]
        return pairs, total or 0

    async def get_user_stats(self, owner_id: uuid.UUID) -> ExecutionStats:
        base = (
            select(Execution)
            .join(Project, Project.id == Execution.project_id)
            .where(Project.owner_id == owner_id)
        )

        total = await self.db.scalar(select(func.count()).select_from(base.subquery()))
        successful = await self.db.scalar(
            select(func.count()).select_from(
                base.where(Execution.status == ExecutionStatus.SUCCESS).subquery()
            )
        )
        failed = await self.db.scalar(
            select(func.count()).select_from(
                base.where(
                    Execution.status.in_([ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT])
                ).subquery()
            )
        )
        last_activity_at = await self.db.scalar(
            select(func.max(Execution.created_at))
            .join(Project, Project.id == Execution.project_id)
            .where(Project.owner_id == owner_id)
        )

        return ExecutionStats(
            total=total or 0,
            successful=successful or 0,
            failed=failed or 0,
            last_activity_at=last_activity_at,
        )

    async def transition(
        self, execution: Execution, to_status: ExecutionStatus, message: str | None = None
    ) -> Execution:
        """Validate and apply a state-machine transition, recording it in
        execution_logs. Raises InvalidExecutionTransitionError if not allowed."""
        from_status = execution.status
        ensure_transition(from_status, to_status)

        execution.status = to_status
        self.db.add(
            ExecutionLog(
                execution_id=execution.id,
                from_status=from_status.value,
                to_status=to_status.value,
                message=message,
            )
        )
        await self.db.flush()
        return execution

    async def create_and_enqueue(
        self,
        project: Project,
        user_id: uuid.UUID,
        file_id: uuid.UUID,
        idempotency_key: str | None,
    ) -> Execution:
        """Create a QUEUED execution and publish its job event to Redis Streams.

        If an Idempotency-Key is supplied and was already used for the same
        (project, file, user) request, the original execution is returned instead
        of creating a duplicate job. A key reused with a *different* request is
        rejected outright rather than silently executed.
        """
        request_hash = _request_hash(project.id, file_id, user_id)

        if idempotency_key:
            existing = await self.db.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.user_id == user_id, IdempotencyKey.key == idempotency_key
                )
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise ApiError(
                        status_code=409,
                        code="IDEMPOTENCY_KEY_CONFLICT",
                        message="This Idempotency-Key was already used for a different request",
                    )
                execution = await self.db.get(Execution, existing.execution_id)
                if execution is not None:
                    return execution

        file = await self.db.scalar(
            select(File).where(File.id == file_id, File.project_id == project.id)
        )
        if file is None:
            raise ApiError(status_code=404, code="FILE_NOT_FOUND", message="File not found")
        if file.type != FileType.FILE:
            raise ApiError(
                status_code=400,
                code="CANNOT_EXECUTE_FOLDER",
                message="Only files can be executed, not folders",
            )

        execution = Execution(
            id=uuid.uuid4(),
            project_id=project.id,
            file_id=file.id,
            user_id=user_id,
            language=project.language,
            status=ExecutionStatus.QUEUED,
        )
        self.db.add(execution)

        if idempotency_key:
            self.db.add(
                IdempotencyKey(
                    key=idempotency_key,
                    user_id=user_id,
                    request_hash=request_hash,
                    execution_id=execution.id,
                )
            )

        # Commit before publishing: the worker reads with its own connection,
        # so publishing first risks a dequeue racing an uncommitted row.
        await self.db.commit()
        await self.db.refresh(execution)

        try:
            await publish_execution_job(execution)
        except RedisError as exc:
            raise ApiError(
                status_code=503,
                code="EXECUTION_QUEUE_UNAVAILABLE",
                message="The execution was recorded but could not be queued for processing. "
                "Please retry.",
            ) from exc

        execution_total.inc()
        return execution

    async def cancel(self, owner_id: uuid.UUID, execution_id: uuid.UUID) -> Execution:
        execution = await self.get_owned(owner_id, execution_id)
        try:
            await self.transition(execution, ExecutionStatus.CANCELLED, message="Cancelled by user")
        except InvalidExecutionTransitionError as exc:
            raise ApiError(
                status_code=409,
                code="EXECUTION_NOT_CANCELLABLE",
                message=f"Cannot cancel an execution that is already {execution.status.value}",
            ) from exc
        record_audit_event(
            self.db,
            owner_id,
            AuditEventType.EXECUTION_CANCELLED,
            resource_type="execution",
            resource_id=execution.id,
        )
        return execution
