from httpx import AsyncClient

from app.core.config import get_settings


async def test_login_rate_limited_after_threshold(client: AsyncClient) -> None:
    limit = get_settings().rate_limit_login_per_minute
    payload = {"email": "ratelimit-login@codeforge.dev", "password": "supersecret123"}
    await client.post("/auth/register", json=payload)
    await client.post("/auth/logout")

    for _ in range(limit):
        response = await client.post("/auth/login", json=payload)
        assert response.status_code == 200

    limited = await client.post("/auth/login", json=payload)
    assert limited.status_code == 429
    body = limited.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in limited.headers


async def test_execute_rate_limited_after_threshold(client: AsyncClient) -> None:
    limit = get_settings().rate_limit_execution_per_minute
    await client.post(
        "/auth/register",
        json={"email": "ratelimit-exec@codeforge.dev", "password": "supersecret123"},
    )
    project = (await client.post("/projects", json={"name": "Rate Limit Project"})).json()["data"]
    file = (
        await client.post(
            f"/projects/{project['id']}/files",
            json={"name": "main.py", "type": "file", "content": "print(1)"},
        )
    ).json()["data"]

    for _ in range(limit):
        response = await client.post(
            f"/projects/{project['id']}/execute", json={"file_id": file["id"]}
        )
        assert response.status_code == 202

    limited = await client.post(f"/projects/{project['id']}/execute", json={"file_id": file["id"]})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


async def test_project_create_rate_limited_after_threshold(client: AsyncClient) -> None:
    limit = get_settings().rate_limit_project_create_per_minute
    await client.post(
        "/auth/register",
        json={"email": "ratelimit-project@codeforge.dev", "password": "supersecret123"},
    )

    for i in range(limit):
        response = await client.post("/projects", json={"name": f"Project {i}"})
        assert response.status_code == 201

    limited = await client.post("/projects", json={"name": "One too many"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


async def test_rate_limits_are_scoped_per_user(client: AsyncClient) -> None:
    """Limits key on user id, not shared global state."""
    limit = get_settings().rate_limit_project_create_per_minute
    await client.post(
        "/auth/register",
        json={"email": "ratelimit-userA@codeforge.dev", "password": "supersecret123"},
    )
    for i in range(limit):
        response = await client.post("/projects", json={"name": f"A Project {i}"})
        assert response.status_code == 201
    assert (await client.post("/projects", json={"name": "one too many"})).status_code == 429

    await client.post("/auth/logout")
    await client.post(
        "/auth/register",
        json={"email": "ratelimit-userB@codeforge.dev", "password": "supersecret123"},
    )
    response = await client.post("/projects", json={"name": "B Project"})
    assert response.status_code == 201
