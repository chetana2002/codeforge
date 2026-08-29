import pytest
from httpx import AsyncClient


@pytest.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    await client.post(
        "/auth/register", json={"email": "owner@codeforge.dev", "password": "ownerpassword123"}
    )
    return client


async def test_create_project(authed_client: AsyncClient) -> None:
    response = await authed_client.post(
        "/projects",
        json={"name": "My First Project", "description": "hello", "language": "python"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "My First Project"
    assert data["language"] == "python"
    assert data["visibility"] == "private"


async def test_create_project_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/projects", json={"name": "Nope"})
    assert response.status_code == 401


async def test_create_project_validates_name(authed_client: AsyncClient) -> None:
    response = await authed_client.post("/projects", json={"name": ""})
    assert response.status_code == 422


async def test_list_projects_paginated(authed_client: AsyncClient) -> None:
    for i in range(3):
        await authed_client.post("/projects", json={"name": f"Project {i}"})

    response = await authed_client.get("/projects", params={"page": 1, "page_size": 2})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 2
    assert len(data["items"]) == 2


async def test_list_projects_search(authed_client: AsyncClient) -> None:
    await authed_client.post("/projects", json={"name": "Data Pipeline", "description": "etl"})
    await authed_client.post("/projects", json={"name": "Web App", "description": "frontend"})

    response = await authed_client.get("/projects", params={"q": "pipeline"})
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Data Pipeline"


async def test_get_project(authed_client: AsyncClient) -> None:
    create_response = await authed_client.post("/projects", json={"name": "Solo"})
    project_id = create_response.json()["data"]["id"]

    response = await authed_client.get(f"/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == project_id


async def test_get_nonexistent_project_returns_404(authed_client: AsyncClient) -> None:
    response = await authed_client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


async def test_update_project(authed_client: AsyncClient) -> None:
    create_response = await authed_client.post("/projects", json={"name": "Old Name"})
    project_id = create_response.json()["data"]["id"]

    response = await authed_client.patch(f"/projects/{project_id}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "New Name"


async def test_delete_project(authed_client: AsyncClient) -> None:
    create_response = await authed_client.post("/projects", json={"name": "Temp"})
    project_id = create_response.json()["data"]["id"]

    delete_response = await authed_client.delete(f"/projects/{project_id}")
    assert delete_response.status_code == 200

    get_response = await authed_client.get(f"/projects/{project_id}")
    assert get_response.status_code == 404


async def test_user_cannot_access_another_users_project(authed_client: AsyncClient) -> None:
    create_response = await authed_client.post("/projects", json={"name": "Private Project"})
    project_id = create_response.json()["data"]["id"]

    # Same client, but re-authenticated as a different user — the project must
    # remain invisible to anyone but its owner.
    await authed_client.post("/auth/logout")
    await authed_client.post(
        "/auth/register",
        json={"email": "intruder@codeforge.dev", "password": "intruderpassword123"},
    )

    response = await authed_client.get(f"/projects/{project_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
