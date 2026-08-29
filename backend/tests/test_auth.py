import pytest
from httpx import AsyncClient


@pytest.fixture
def register_payload() -> dict[str, str]:
    return {"email": "ada@codeforge.dev", "password": "supersecret123"}


async def test_register_creates_user_and_sets_cookies(
    client: AsyncClient, register_payload: dict[str, str]
) -> None:
    response = await client.post("/auth/register", json=register_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["email"] == register_payload["email"]
    assert "id" in body["data"]
    assert body["error"] is None
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


async def test_register_duplicate_email_rejected(
    client: AsyncClient, register_payload: dict[str, str]
) -> None:
    first = await client.post("/auth/register", json=register_payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=register_payload)
    assert second.status_code == 409
    body = second.json()
    assert body["data"] is None
    assert body["error"]["code"] == "EMAIL_ALREADY_EXISTS"


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json={"email": "short@codeforge.dev", "password": "short"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_login_success(client: AsyncClient, register_payload: dict[str, str]) -> None:
    await client.post("/auth/register", json=register_payload)

    response = await client.post("/auth/login", json=register_payload)
    assert response.status_code == 200
    assert response.json()["data"]["email"] == register_payload["email"]
    assert "access_token" in response.cookies


async def test_login_invalid_credentials(
    client: AsyncClient, register_payload: dict[str, str]
) -> None:
    await client.post("/auth/register", json=register_payload)

    response = await client.post(
        "/auth/login", json={"email": register_payload["email"], "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_login_unknown_email(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "nobody@codeforge.dev", "password": "whatever123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_me_rejects_malformed_token(client: AsyncClient) -> None:
    client.cookies.set("access_token", "not-a-real-jwt")
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_me_returns_current_user_after_login(
    client: AsyncClient, register_payload: dict[str, str]
) -> None:
    await client.post("/auth/register", json=register_payload)

    response = await client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["data"]["email"] == register_payload["email"]


async def test_logout_clears_session(client: AsyncClient, register_payload: dict[str, str]) -> None:
    await client.post("/auth/register", json=register_payload)
    assert (await client.get("/auth/me")).status_code == 200

    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["data"]["logged_out"] is True

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 401


async def test_refresh_rotates_session_and_invalidates_old_token(
    client: AsyncClient, register_payload: dict[str, str]
) -> None:
    await client.post("/auth/register", json=register_payload)
    old_refresh_token = client.cookies.get("refresh_token")
    assert old_refresh_token is not None

    refresh_response = await client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    new_refresh_token = client.cookies.get("refresh_token")
    assert new_refresh_token is not None
    assert new_refresh_token != old_refresh_token

    client.cookies.set("refresh_token", old_refresh_token)
    reuse_response = await client.post("/auth/refresh")
    assert reuse_response.status_code == 401
    assert reuse_response.json()["error"]["code"] == "SESSION_EXPIRED"


async def test_refresh_without_cookie_rejected(client: AsyncClient) -> None:
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
