"""Redis pub/sub notifications for execution status transitions.

Separate from the job queue (codeforge:executions, a Redis Stream): this is a
fire-and-forget broadcast so the API can push live status to a connected SSE
client without polling Postgres. Pub/sub delivers at-most-once with no
replay — a subscriber that isn't listening at publish time simply misses the
message — which is fine here because the API always reads current state from
Postgres directly (via ExecutionService.get_owned) around the subscription
window, rather than treating a pub/sub message as the source of truth.
"""

import json
import uuid

from redis.asyncio import Redis

EXECUTION_UPDATES_CHANNEL = "codeforge:execution-updates"


async def publish_status_update(redis: Redis, execution_id: uuid.UUID, status: str) -> None:
    payload = json.dumps({"execution_id": str(execution_id), "status": status})
    await redis.publish(EXECUTION_UPDATES_CHANNEL, payload)
