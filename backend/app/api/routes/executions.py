import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.application.services.execution_service import ExecutionService
from app.application.services.project_service import ProjectService
from app.core.config import get_settings
from app.core.rate_limit import execution_rate_limit
from app.domain.enums.execution_status import is_terminal
from app.domain.models.execution import Execution
from app.domain.models.user import User
from app.infrastructure.database.session import get_db
from app.infrastructure.redis.client import get_redis
from app.infrastructure.redis.pubsub import EXECUTION_UPDATES_CHANNEL
from app.schemas.envelope import Envelope
from app.schemas.execution import (
    ExecuteRequest,
    ExecutionResponse,
    ExecutionStats,
    ExecutionSummary,
    ExecutionWithProject,
)
from app.schemas.pagination import Page, PageParams

router = APIRouter(tags=["executions"])


@router.post(
    "/projects/{project_id}/execute",
    response_model=Envelope[ExecutionResponse],
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(execution_rate_limit())],
)
async def execute_project_file(
    project_id: uuid.UUID,
    payload: ExecuteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[ExecutionResponse]:
    project = await ProjectService(db).get_owned(current_user.id, project_id)
    execution = await ExecutionService(db).create_and_enqueue(
        project, current_user.id, payload.file_id, idempotency_key
    )
    return Envelope(data=ExecutionResponse.model_validate(execution))


@router.post("/executions/{execution_id}/cancel", response_model=Envelope[ExecutionResponse])
async def cancel_execution(
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[ExecutionResponse]:
    execution = await ExecutionService(db).cancel(current_user.id, execution_id)
    await db.commit()
    return Envelope(data=ExecutionResponse.model_validate(execution))


def _sse_event(execution: Execution) -> str:
    payload = ExecutionResponse.model_validate(execution).model_dump(mode="json")
    return f"data: {json.dumps(payload)}\n\n"


@router.get("/executions/{execution_id}/stream")
async def stream_execution(
    execution_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE stream of an execution's status until terminal or max duration elapses.

    Ownership is checked outside the generator so an unauthorized/unknown id
    gets a plain 404 instead of a 200 stream that immediately errors.
    """
    settings = get_settings()
    service = ExecutionService(db)
    await service.get_owned(current_user.id, execution_id)

    async def event_generator() -> AsyncIterator[str]:
        redis = get_redis()
        pubsub = redis.pubsub()
        # Subscribe before the first state read so a transition that lands in the
        # gap between "check current state" and "start listening" can't be missed.
        await pubsub.subscribe(EXECUTION_UPDATES_CHANNEL)
        try:
            execution = await service.get_owned(current_user.id, execution_id)
            yield _sse_event(execution)
            if is_terminal(execution.status):
                return

            deadline = time.monotonic() + settings.execution_stream_max_seconds
            while time.monotonic() < deadline:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=settings.execution_stream_keepalive_seconds,
                )
                if message is None:
                    yield ": keepalive\n\n"
                    continue

                try:
                    data = json.loads(message["data"])
                except (TypeError, ValueError):
                    continue
                if data.get("execution_id") != str(execution_id):
                    continue

                # Force a real SELECT — the identity map would otherwise hand
                # back this session's stale copy of the row.
                db.expire_all()
                execution = await service.get_owned(current_user.id, execution_id)
                yield _sse_event(execution)
                if is_terminal(execution.status):
                    break
        finally:
            await pubsub.unsubscribe(EXECUTION_UPDATES_CHANNEL)
            await pubsub.aclose()  # type: ignore[no-untyped-call]  # redis-py stub gap
            await db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/executions/stats", response_model=Envelope[ExecutionStats])
async def get_execution_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[ExecutionStats]:
    stats = await ExecutionService(db).get_user_stats(current_user.id)
    return Envelope(data=stats)


@router.get("/executions", response_model=Envelope[Page[ExecutionWithProject]])
async def list_my_executions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[Page[ExecutionWithProject]]:
    params = PageParams(page=page, page_size=page_size)
    pairs, total = await ExecutionService(db).list_for_user(current_user.id, params)
    items = [
        ExecutionWithProject(
            **ExecutionSummary.model_validate(execution).model_dump(), project_name=project_name
        )
        for execution, project_name in pairs
    ]
    return Envelope(data=Page[ExecutionWithProject].create(items=items, total=total, params=params))


@router.get("/executions/{execution_id}", response_model=Envelope[ExecutionResponse])
async def get_execution(
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[ExecutionResponse]:
    execution = await ExecutionService(db).get_owned(current_user.id, execution_id)
    return Envelope(data=ExecutionResponse.model_validate(execution))


@router.get("/projects/{project_id}/executions", response_model=Envelope[Page[ExecutionSummary]])
async def list_project_executions(
    project_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Envelope[Page[ExecutionSummary]]:
    project = await ProjectService(db).get_owned(current_user.id, project_id)
    params = PageParams(page=page, page_size=page_size)
    items, total = await ExecutionService(db).list_for_project(project.id, params)
    return Envelope(
        data=Page[ExecutionSummary].create(
            items=[ExecutionSummary.model_validate(e) for e in items],
            total=total,
            params=params,
        )
    )
