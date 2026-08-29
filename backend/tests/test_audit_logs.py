from httpx import AsyncClient


async def _event_types(client: AsyncClient) -> list[str]:
    response = await client.get("/audit-logs", params={"page_size": 100})
    assert response.status_code == 200
    return [item["event_type"] for item in response.json()["data"]["items"]]


async def test_login_and_logout_are_audited(client: AsyncClient) -> None:
    payload = {"email": "audit-auth@codeforge.dev", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    # register() itself creates a session, so this first logout is one real
    # logout, not a no-op — it's counted below alongside the explicit one.
    await client.post("/auth/logout")
    await client.post("/auth/login", json=payload)

    events = await _event_types(client)
    assert "login" in events

    await client.post("/auth/logout")
    await client.post("/auth/login", json=payload)
    events = await _event_types(client)
    assert events.count("logout") == 2


async def test_project_and_file_lifecycle_is_audited(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "audit-lifecycle@codeforge.dev", "password": "supersecret123"},
    )
    project = (await client.post("/projects", json={"name": "Audit Project"})).json()["data"]
    file = (
        await client.post(
            f"/projects/{project['id']}/files",
            json={"name": "main.py", "type": "file", "content": "print(1)"},
        )
    ).json()["data"]
    await client.delete(f"/projects/{project['id']}/files/{file['id']}")
    await client.delete(f"/projects/{project['id']}")

    events = await _event_types(client)
    assert "project_created" in events
    assert "file_created" in events
    assert "file_deleted" in events
    assert "project_deleted" in events


async def test_execution_cancel_is_audited(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "audit-execution@codeforge.dev", "password": "supersecret123"},
    )
    project = (await client.post("/projects", json={"name": "Audit Exec Project"})).json()["data"]
    file = (
        await client.post(
            f"/projects/{project['id']}/files",
            json={"name": "main.py", "type": "file", "content": "print(1)"},
        )
    ).json()["data"]
    execution = (
        await client.post(f"/projects/{project['id']}/execute", json={"file_id": file["id"]})
    ).json()["data"]
    await client.post(f"/executions/{execution['id']}/cancel")

    events = await _event_types(client)
    assert "execution_cancelled" in events


async def test_audit_logs_are_scoped_to_the_requesting_user(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"email": "audit-userA@codeforge.dev", "password": "supersecret123"},
    )
    await client.post("/projects", json={"name": "User A Project"})

    await client.post("/auth/logout")
    await client.post(
        "/auth/register",
        json={"email": "audit-userB@codeforge.dev", "password": "supersecret123"},
    )

    events = await _event_types(client)
    # Only user B's own register-triggered activity (none, since register isn't
    # audited) plus their login-equivalent session creation should show up —
    # user A's project_created event must not leak across accounts.
    assert "project_created" not in events


async def test_audit_logs_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/audit-logs")
    assert response.status_code == 401
