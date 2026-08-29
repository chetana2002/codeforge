import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.execution_service import ExecutionService
from app.domain.enums.execution_status import ExecutionStatus, InvalidExecutionTransitionError
from app.domain.enums.language import Language
from app.domain.models.execution import Execution
from app.domain.models.execution_log import ExecutionLog
from app.infrastructure.redis.client import get_redis
from app.infrastructure.redis.streams import EXECUTION_STREAM_KEY


@pytest.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    await client.post(
        "/auth/register", json={"email": "runner@codeforge.dev", "password": "runnerpassword123"}
    )
    return client


@pytest.fixture
async def project_with_file(authed_client: AsyncClient) -> dict[str, str]:
    project = (
        await authed_client.post("/projects", json={"name": "Execution History Project"})
    ).json()["data"]
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
    status: ExecutionStatus = ExecutionStatus.SUCCESS,
) -> Execution:
    execution = Execution(
        project_id=uuid.UUID(project_id),
        file_id=uuid.UUID(file_id),
        user_id=uuid.UUID(user_id),
        language=Language.PYTHON,
        status=status,
        stdout="hello\n" if status == ExecutionStatus.SUCCESS else None,
        exit_code=0 if status == ExecutionStatus.SUCCESS else None,
        duration_ms=142,
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


async def test_get_execution(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    execution = await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
    )

    response = await authed_client.get(f"/executions/{execution.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "success"
    assert data["stdout"] == "hello\n"


async def test_get_nonexistent_execution_returns_404(authed_client: AsyncClient) -> None:
    response = await authed_client.get(f"/executions/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXECUTION_NOT_FOUND"


async def test_execution_access_requires_ownership(
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
        json={"email": "execution-intruder@codeforge.dev", "password": "intruderpassword123"},
    )

    response = await authed_client.get(f"/executions/{execution.id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXECUTION_NOT_FOUND"


async def test_list_project_executions_paginated(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    for _ in range(3):
        await _insert_execution(
            db_session,
            project_id=project_with_file["project_id"],
            file_id=project_with_file["file_id"],
            user_id=me["id"],
        )

    response = await authed_client.get(
        f"/projects/{project_with_file['project_id']}/executions", params={"page_size": 2}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert "stdout" not in data["items"][0]


async def test_execution_service_transition_writes_audit_log(
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

    service = ExecutionService(db_session)
    updated = await service.transition(
        execution, ExecutionStatus.RUNNING, message="worker picked up job"
    )
    assert updated.status == ExecutionStatus.RUNNING

    logs = (
        await db_session.scalars(
            select(ExecutionLog).where(ExecutionLog.execution_id == execution.id)
        )
    ).all()
    assert len(logs) == 1
    assert logs[0].from_status == "queued"
    assert logs[0].to_status == "running"
    assert logs[0].message == "worker picked up job"


async def test_execution_service_transition_rejects_invalid_transition(
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

    service = ExecutionService(db_session)
    with pytest.raises(InvalidExecutionTransitionError):
        await service.transition(execution, ExecutionStatus.SUCCESS)


async def test_list_executions_requires_project_ownership(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    await authed_client.post("/auth/logout")
    await authed_client.post(
        "/auth/register",
        json={"email": "list-intruder@codeforge.dev", "password": "intruderpassword123"},
    )

    response = await authed_client.get(f"/projects/{project_with_file['project_id']}/executions")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


async def test_execute_creates_queued_execution_and_publishes_job(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    response = await authed_client.post(
        f"/projects/{project_with_file['project_id']}/execute",
        json={"file_id": project_with_file["file_id"]},
    )
    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "queued"
    assert data["file_id"] == project_with_file["file_id"]

    redis = get_redis()
    entries = await redis.xrange(EXECUTION_STREAM_KEY, "-", "+")
    assert len(entries) == 1
    _entry_id, fields = entries[0]
    assert fields["execution_id"] == data["id"]
    assert fields["project_id"] == project_with_file["project_id"]
    assert fields["language"] == "python"


async def test_execute_requires_project_ownership(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    await authed_client.post("/auth/logout")
    await authed_client.post(
        "/auth/register",
        json={"email": "execute-intruder@codeforge.dev", "password": "intruderpassword123"},
    )

    response = await authed_client.post(
        f"/projects/{project_with_file['project_id']}/execute",
        json={"file_id": project_with_file["file_id"]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


async def test_execute_rejects_nonexistent_file(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    response = await authed_client.post(
        f"/projects/{project_with_file['project_id']}/execute",
        json={"file_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FILE_NOT_FOUND"


async def test_execute_rejects_folder(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    folder = (
        await authed_client.post(
            f"/projects/{project_with_file['project_id']}/files",
            json={"name": "src", "type": "folder"},
        )
    ).json()["data"]

    response = await authed_client.post(
        f"/projects/{project_with_file['project_id']}/execute",
        json={"file_id": folder["id"]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CANNOT_EXECUTE_FOLDER"


async def test_execute_idempotency_key_returns_same_execution(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    headers = {"Idempotency-Key": "retry-key-1"}
    first = await authed_client.post(
        f"/projects/{project_with_file['project_id']}/execute",
        json={"file_id": project_with_file["file_id"]},
        headers=headers,
    )
    second = await authed_client.post(
        f"/projects/{project_with_file['project_id']}/execute",
        json={"file_id": project_with_file["file_id"]},
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    redis = get_redis()
    entries = await redis.xrange(EXECUTION_STREAM_KEY, "-", "+")
    assert len(entries) == 1  # only the first request published a job


async def test_execute_idempotency_key_conflict_on_different_request(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    headers = {"Idempotency-Key": "retry-key-2"}
    await authed_client.post(
        f"/projects/{project_with_file['project_id']}/execute",
        json={"file_id": project_with_file["file_id"]},
        headers=headers,
    )

    other_file = (
        await authed_client.post(
            f"/projects/{project_with_file['project_id']}/files",
            json={"name": "other.py", "type": "file", "content": "print(2)"},
        )
    ).json()["data"]

    response = await authed_client.post(
        f"/projects/{project_with_file['project_id']}/execute",
        json={"file_id": other_file["id"]},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


async def test_cancel_queued_execution(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    execution = (
        await authed_client.post(
            f"/projects/{project_with_file['project_id']}/execute",
            json={"file_id": project_with_file["file_id"]},
        )
    ).json()["data"]

    response = await authed_client.post(f"/executions/{execution['id']}/cancel")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "cancelled"


async def test_cancel_terminal_execution_rejected(
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

    response = await authed_client.post(f"/executions/{execution.id}/cancel")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXECUTION_NOT_CANCELLABLE"


async def test_cancel_requires_ownership(
    authed_client: AsyncClient, project_with_file: dict[str, str]
) -> None:
    execution = (
        await authed_client.post(
            f"/projects/{project_with_file['project_id']}/execute",
            json={"file_id": project_with_file["file_id"]},
        )
    ).json()["data"]

    await authed_client.post("/auth/logout")
    await authed_client.post(
        "/auth/register",
        json={"email": "cancel-intruder@codeforge.dev", "password": "intruderpassword123"},
    )

    response = await authed_client.post(f"/executions/{execution['id']}/cancel")
    assert response.status_code == 404


async def test_list_my_executions_across_projects(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
    )

    other_project = (await authed_client.post("/projects", json={"name": "Second Project"})).json()[
        "data"
    ]
    other_file = (
        await authed_client.post(
            f"/projects/{other_project['id']}/files",
            json={"name": "app.py", "type": "file", "content": "print(2)"},
        )
    ).json()["data"]
    await _insert_execution(
        db_session, project_id=other_project["id"], file_id=other_file["id"], user_id=me["id"]
    )

    response = await authed_client.get("/executions")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 2
    project_names = {item["project_name"] for item in data["items"]}
    assert project_names == {"Execution History Project", "Second Project"}


async def test_list_my_executions_excludes_other_users(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
    )

    await authed_client.post("/auth/logout")
    await authed_client.post(
        "/auth/register",
        json={"email": "stats-intruder@codeforge.dev", "password": "intruderpassword123"},
    )

    response = await authed_client.get("/executions")
    assert response.json()["data"]["total"] == 0


async def test_execution_stats(
    authed_client: AsyncClient, project_with_file: dict[str, str], db_session: AsyncSession
) -> None:
    me = (await authed_client.get("/auth/me")).json()["data"]
    await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
        status=ExecutionStatus.SUCCESS,
    )
    await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
        status=ExecutionStatus.FAILED,
    )
    await _insert_execution(
        db_session,
        project_id=project_with_file["project_id"],
        file_id=project_with_file["file_id"],
        user_id=me["id"],
        status=ExecutionStatus.QUEUED,
    )

    response = await authed_client.get("/executions/stats")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["successful"] == 1
    assert data["failed"] == 1
    assert data["last_activity_at"] is not None


async def test_execution_stats_empty_for_new_user(authed_client: AsyncClient) -> None:
    response = await authed_client.get("/executions/stats")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {"total": 0, "successful": 0, "failed": 0, "last_activity_at": None}
