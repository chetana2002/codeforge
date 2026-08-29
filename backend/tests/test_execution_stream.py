import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums.execution_status import ExecutionStatus
from app.domain.enums.language import Language
from app.domain.models.execution import Execution
from app.infrastructure.redis.client import get_redis
from app.infrastructure.redis.pubsub import EXECUTION_UPDATES_CHANNEL


@pytest.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    await client.post(
        "/auth/register",
        json={"email": "streamer@codeforge.dev", "password": "streamerpassword123"},
    )
    return client


@pytest.fixture
async def project_with_file(authed_client: AsyncClient) -> dict[str, str]:
    response = await authed_client.post("/projects", json={"name": "Stream Project"})
    project = response.json()["data"]
    file = (
        await authed_client.post(
            f"/projects/{project['id']}/files",
            json={"name": "main.py", "type": "file", "content": "print(1)"},
        )
    ).json()["data"]
    return {"project_id": project["id"], "file_id": file["id"]}


async def _insert_execution(
    db_session: AsyncSession,
    *,
    project_id: str,
    file_id: str,
    user_id: str,
    status: ExecutionStatus = ExecutionStatus.QUEUED,
) -> Execution:
    execution = Execution(
        project_id=uuid.UUID(project_id),
        file_id=uuid.UUID(file_id),
        user_id=uuid.UUID(user_id),
        language=Language.PYTHON,
        status=status,
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


async def _next_data_event(lines: AsyncIterator[str]) -> dict[str, object]:
    """Pulls from a single shared aiter_lines() iterator — httpx raises
    StreamConsumed if it's called more than once per response."""
    async for line in lines:
        if line.startswith("data: "):
            return dict(json.loads(line[len("data: ") :]))
    raise AssertionError("stream ended before yielding a data event")


async def test_stream_requires_ownership(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    execution = await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
    )

    await authed_client.post("/auth/logout")
    await authed_client.post(
        "/auth/register",
        json={"email": "stream-intruder@codeforge.dev", "password": "intruderpassword123"},
    )

    response = await authed_client.get(f"/executions/{execution.id}/stream")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXECUTION_NOT_FOUND"


async def test_stream_sends_initial_state_immediately(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    execution = await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
        status=ExecutionStatus.SUCCESS,
    )

    async with authed_client.stream("GET", f"/executions/{execution.id}/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        event = await _next_data_event(response.aiter_lines())
        assert event["id"] == str(execution.id)
        assert event["status"] == "success"


async def test_stream_closes_after_terminal_state(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    execution = await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
        status=ExecutionStatus.FAILED,
    )

    async with authed_client.stream("GET", f"/executions/{execution.id}/stream") as response:
        lines = response.aiter_lines()
        await _next_data_event(lines)

        # A terminal execution ends the stream right after its one event.
        async def drain() -> list[str]:
            return [line async for line in lines]

        remaining_lines = await asyncio.wait_for(drain(), timeout=5)
        assert not any(line.startswith("data: ") for line in remaining_lines)


async def test_stream_pushes_live_update_via_pubsub(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    execution = await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
        status=ExecutionStatus.QUEUED,
    )

    async def simulate_worker_transition() -> None:
        redis = get_redis()
        await asyncio.sleep(0.3)
        execution.status = ExecutionStatus.RUNNING
        await db_session.commit()
        await redis.publish(
            EXECUTION_UPDATES_CHANNEL,
            json.dumps({"execution_id": str(execution.id), "status": "running"}),
        )

        # Drive to terminal so the generator ends itself — the test transport
        # never reports a client disconnect, so relying on that would leak
        # a connection past this test's event loop.
        await asyncio.sleep(0.3)
        execution.status = ExecutionStatus.SUCCESS
        await db_session.commit()
        await redis.publish(
            EXECUTION_UPDATES_CHANNEL,
            json.dumps({"execution_id": str(execution.id), "status": "success"}),
        )

    task = asyncio.create_task(simulate_worker_transition())
    try:
        async with authed_client.stream("GET", f"/executions/{execution.id}/stream") as response:
            lines = response.aiter_lines()
            first = await _next_data_event(lines)
            assert first["status"] == "queued"

            second = await asyncio.wait_for(_next_data_event(lines), timeout=5)
            assert second["status"] == "running"

            third = await asyncio.wait_for(_next_data_event(lines), timeout=5)
            assert third["status"] == "success"
    finally:
        await task
