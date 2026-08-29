"""Redis Streams consumer for execution jobs.

At-least-once delivery via a consumer group: XACK only on successful
handling, so an unhandled exception leaves a message for XAUTOCLAIM to
reclaim and retry. See docs/execution-engine.md and docs/failure-scenarios.md
for delivery semantics and the known RUNNING-crash gap.
"""

import asyncio

import structlog
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from config import WorkerSettings
from execution_manager import ExecutionManager
from metrics import worker_job_failures_total, worker_jobs_total

logger = structlog.get_logger(__name__)

CLAIM_IDLE_MS = 60_000
BLOCK_MS = 5_000
RECLAIM_BATCH_SIZE = 10


class StreamConsumer:
    def __init__(self, redis: Redis, settings: WorkerSettings, manager: ExecutionManager):
        self.redis = redis
        self.settings = settings
        self.manager = manager
        self._shutdown = asyncio.Event()

    def request_shutdown(self) -> None:
        self._shutdown.set()

    async def _ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                self.settings.stream_key, self.settings.consumer_group, id="0", mkstream=True
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def run(self) -> None:
        await self._ensure_group()
        logger.info(
            "consumer_started",
            stream=self.settings.stream_key,
            group=self.settings.consumer_group,
            consumer=self.settings.consumer_name,
        )

        while not self._shutdown.is_set():
            await self._reclaim_stale_pending()
            await self._read_and_process_new()

        logger.info("consumer_stopped")

    async def _reclaim_stale_pending(self) -> None:
        try:
            _cursor, claimed, _deleted = await self.redis.xautoclaim(
                self.settings.stream_key,
                self.settings.consumer_group,
                self.settings.consumer_name,
                min_idle_time=CLAIM_IDLE_MS,
                start_id="0-0",
                count=RECLAIM_BATCH_SIZE,
            )
        except ResponseError as exc:
            logger.error("xautoclaim_failed", error=str(exc))
            return

        for message_id, fields in claimed:
            logger.warning(
                "execution_job_reclaimed",
                message_id=message_id,
                execution_id=fields.get("execution_id"),
            )
            await self._process(message_id, fields)

    async def _read_and_process_new(self) -> None:
        try:
            response = await self.redis.xreadgroup(
                self.settings.consumer_group,
                self.settings.consumer_name,
                {self.settings.stream_key: ">"},
                count=1,
                block=BLOCK_MS,
            )
        except ResponseError as exc:
            logger.error("xreadgroup_failed", error=str(exc))
            await asyncio.sleep(1)
            return

        if not response:
            return

        for _stream_key, messages in response:
            for message_id, fields in messages:
                await self._process(message_id, fields)

    async def _process(self, message_id: str, fields: dict[str, str]) -> None:
        worker_jobs_total.inc()
        try:
            await self.manager.handle_event(fields)
        except Exception:
            worker_job_failures_total.inc()
            logger.exception(
                "execution_job_failed_unexpectedly",
                message_id=message_id,
                execution_id=fields.get("execution_id"),
            )
            return  # left un-ACKed: eligible for XAUTOCLAIM retry

        await self.redis.xack(self.settings.stream_key, self.settings.consumer_group, message_id)
