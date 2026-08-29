"""Redis pub/sub notifications for execution status transitions.

Fire-and-forget broadcast, separate from the job queue — lets the API push
live status to an SSE client without polling Postgres. At-most-once
delivery is fine here since the API always re-reads state from Postgres.
"""

import json
import uuid

from redis.asyncio import Redis

EXECUTION_UPDATES_CHANNEL = "codeforge:execution-updates"


async def publish_status_update(redis: Redis, execution_id: uuid.UUID, status: str) -> None:
    payload = json.dumps({"execution_id": str(execution_id), "status": status})
    await redis.publish(EXECUTION_UPDATES_CHANNEL, payload)
