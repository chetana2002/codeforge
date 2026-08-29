"""Redis Streams producer for execution jobs.

The API only ever XADDs; the worker (worker/consumer.py) reads via a
consumer group, giving at-least-once delivery. See docs/execution-engine.md.
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
    """XADD the job event; returns the stream entry ID. Raises RedisError if unreachable."""
    redis = get_redis()
    event = build_execution_event(execution)
    entry_id = await redis.xadd(EXECUTION_STREAM_KEY, cast(dict[FieldT, FieldT], event))
    return str(entry_id)
