import pytest
from httpx import AsyncClient


@pytest.fixture
async def project(authed_client: AsyncClient) -> dict[str, str]:
    response = await authed_client.post("/projects", json={"name": "File Tree Project"})
    project: dict[str, str] = response.json()["data"]
    return project


@pytest.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    await client.post(
        "/auth/register", json={"email": "filer@codeforge.dev", "password": "filerpassword123"}
    )
    return client


async def test_create_root_file(authed_client: AsyncClient, project: dict[str, str]) -> None:
    response = await authed_client.post(
        f"/projects/{project['id']}/files",
        json={"name": "README.md", "type": "file", "content": "# Hello"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "README.md"
    assert data["parent_id"] is None
    assert data["content"] == "# Hello"


async def test_create_folder_and_nested_file(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    folder_response = await authed_client.post(
        f"/projects/{project['id']}/files", json={"name": "src", "type": "folder"}
    )
    folder_id = folder_response.json()["data"]["id"]

    file_response = await authed_client.post(
        f"/projects/{project['id']}/files",
        json={"parent_id": folder_id, "name": "main.py", "type": "file", "content": "print(1)"},
    )
    assert file_response.status_code == 201
    assert file_response.json()["data"]["parent_id"] == folder_id


async def test_folder_cannot_have_content(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    response = await authed_client.post(
        f"/projects/{project['id']}/files",
        json={"name": "src", "type": "folder", "content": "not allowed"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FOLDER_CANNOT_HAVE_CONTENT"


async def test_duplicate_sibling_name_conflict(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    await authed_client.post(
        f"/projects/{project['id']}/files", json={"name": "main.py", "type": "file"}
    )
    response = await authed_client.post(
        f"/projects/{project['id']}/files", json={"name": "main.py", "type": "file"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FILE_ALREADY_EXISTS"


async def test_same_name_allowed_in_different_folders(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    folder_a = (
        await authed_client.post(
            f"/projects/{project['id']}/files", json={"name": "a", "type": "folder"}
        )
    ).json()["data"]["id"]
    folder_b = (
        await authed_client.post(
            f"/projects/{project['id']}/files", json={"name": "b", "type": "folder"}
        )
    ).json()["data"]["id"]

    r1 = await authed_client.post(
        f"/projects/{project['id']}/files",
        json={"parent_id": folder_a, "name": "index.js", "type": "file"},
    )
    r2 = await authed_client.post(
        f"/projects/{project['id']}/files",
        json={"parent_id": folder_b, "name": "index.js", "type": "file"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201


@pytest.mark.parametrize("bad_name", ["../etc/passwd", "a/b", "a\\b", "..", ".", ""])
async def test_rejects_path_traversal_style_names(
    authed_client: AsyncClient, project: dict[str, str], bad_name: str
) -> None:
    response = await authed_client.post(
        f"/projects/{project['id']}/files", json={"name": bad_name, "type": "file"}
    )
    assert response.status_code == 422


async def test_create_file_with_missing_parent_returns_404(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    response = await authed_client.post(
        f"/projects/{project['id']}/files",
        json={
            "parent_id": "00000000-0000-0000-0000-000000000000",
            "name": "main.py",
            "type": "file",
        },
    )
    assert response.status_code == 404


async def test_create_file_with_file_as_parent_rejected(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    file_id = (
        await authed_client.post(
            f"/projects/{project['id']}/files", json={"name": "main.py", "type": "file"}
        )
    ).json()["data"]["id"]

    response = await authed_client.post(
        f"/projects/{project['id']}/files",
        json={"parent_id": file_id, "name": "nested.py", "type": "file"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PARENT_NOT_A_FOLDER"


async def test_list_files_returns_tree(authed_client: AsyncClient, project: dict[str, str]) -> None:
    await authed_client.post(
        f"/projects/{project['id']}/files", json={"name": "README.md", "type": "file"}
    )
    await authed_client.post(
        f"/projects/{project['id']}/files", json={"name": "src", "type": "folder"}
    )

    response = await authed_client.get(f"/projects/{project['id']}/files")
    assert response.status_code == 200
    items = response.json()["data"]
    assert {item["name"] for item in items} == {"README.md", "src"}
    assert "content" not in items[0]


async def test_update_file_content(authed_client: AsyncClient, project: dict[str, str]) -> None:
    file_id = (
        await authed_client.post(
            f"/projects/{project['id']}/files",
            json={"name": "main.py", "type": "file", "content": "print(1)"},
        )
    ).json()["data"]["id"]

    response = await authed_client.patch(
        f"/projects/{project['id']}/files/{file_id}", json={"content": "print(2)"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["content"] == "print(2)"


async def test_rename_file(authed_client: AsyncClient, project: dict[str, str]) -> None:
    file_id = (
        await authed_client.post(
            f"/projects/{project['id']}/files", json={"name": "old.py", "type": "file"}
        )
    ).json()["data"]["id"]

    response = await authed_client.patch(
        f"/projects/{project['id']}/files/{file_id}", json={"name": "new.py"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "new.py"


async def test_move_folder_into_itself_rejected(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    folder_id = (
        await authed_client.post(
            f"/projects/{project['id']}/files", json={"name": "src", "type": "folder"}
        )
    ).json()["data"]["id"]

    response = await authed_client.patch(
        f"/projects/{project['id']}/files/{folder_id}", json={"parent_id": folder_id}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MOVE"


async def test_move_folder_into_own_descendant_rejected(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    parent_id = (
        await authed_client.post(
            f"/projects/{project['id']}/files", json={"name": "parent", "type": "folder"}
        )
    ).json()["data"]["id"]
    child_id = (
        await authed_client.post(
            f"/projects/{project['id']}/files",
            json={"parent_id": parent_id, "name": "child", "type": "folder"},
        )
    ).json()["data"]["id"]

    response = await authed_client.patch(
        f"/projects/{project['id']}/files/{parent_id}", json={"parent_id": child_id}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MOVE"


async def test_delete_folder_cascades_to_children(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    folder_id = (
        await authed_client.post(
            f"/projects/{project['id']}/files", json={"name": "src", "type": "folder"}
        )
    ).json()["data"]["id"]
    child_id = (
        await authed_client.post(
            f"/projects/{project['id']}/files",
            json={"parent_id": folder_id, "name": "main.py", "type": "file"},
        )
    ).json()["data"]["id"]

    delete_response = await authed_client.delete(f"/projects/{project['id']}/files/{folder_id}")
    assert delete_response.status_code == 200

    get_response = await authed_client.get(f"/projects/{project['id']}/files/{child_id}")
    assert get_response.status_code == 404


async def test_file_access_requires_project_ownership(
    authed_client: AsyncClient, project: dict[str, str]
) -> None:
    await authed_client.post("/auth/logout")
    await authed_client.post(
        "/auth/register",
        json={"email": "file-intruder@codeforge.dev", "password": "intruderpassword123"},
    )

    response = await authed_client.get(f"/projects/{project['id']}/files")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
