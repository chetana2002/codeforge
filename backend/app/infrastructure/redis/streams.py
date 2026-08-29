"""Redis Streams producer for execution jobs.

Delivery semantics: the API only ever XADDs — it never reads the stream. The
worker (see worker/consumer.py) reads via a consumer group with XREADGROUP and
XACKs only after the job reaches a terminal state, giving *at-least-once*
delivery: if a worker crashes mid-job, the message stays in the group's
Pending Entries List and another consumer can XCLAIM and retry it. Because
retries are possible, job handling must be idempotent from the worker's point
of view — it always re-checks the execution's current status before acting,
so a duplicate delivery of an already-terminal job is a no-op.

If Redis itself is unreachable, publish_execution_job raises RedisError and the
caller is expected to fail the request rather than leave a QUEUED execution
that can never be picked up (see ExecutionService.create_and_enqueue).
"""

import uuid
from datetime import UTC, datetime
from typing import cast

from redis.typing import FieldT

from app.domain.models.execution import Execution
from app.infrastructure.redis.client import get_redis

EXECUTION_STREAM_KEY = "codeforge:executions"


def build_execution_event(execution: Execution) -> dict[str, str]:
    return {
        "event_id": str(uuid.uuid4()),
        "execution_id": str(execution.id),
        "project_id": str(execution.project_id),
        "file_id": str(execution.file_id),
        "user_id": str(execution.user_id),
        "language": execution.language.value,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def publish_execution_job(execution: Execution) -> str:
    """XADD the job event onto the execution stream. Returns the stream entry ID.

    Raises redis.exceptions.RedisError (propagated) if Redis is unreachable —
    callers must not treat a failed publish as a successfully queued job.
    """
    redis = get_redis()
    event = build_execution_event(execution)
    entry_id = await redis.xadd(EXECUTION_STREAM_KEY, cast(dict[FieldT, FieldT], event))
    return str(entry_id)
