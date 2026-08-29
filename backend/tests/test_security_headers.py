from httpx import AsyncClient


async def test_security_headers_present_on_every_response(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in response.headers


async def test_hsts_not_set_outside_production(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert "strict-transport-security" not in response.headers
