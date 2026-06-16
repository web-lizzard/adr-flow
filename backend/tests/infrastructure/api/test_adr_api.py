"""ADR API integration tests."""

from uuid import UUID

from domain.adr.template import ADR_STARTER_TEMPLATE
from fastapi.testclient import TestClient
from sqlalchemy import text


def _register_user(client: TestClient, email: str = "adr-user@example.com") -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 201


def _create_adr(client: TestClient, title: str = "My First ADR") -> UUID:
    response = client.post("/api/adrs", json={"title": title})
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_create_adr_with_title_returns_201_with_starter_template(auth_client) -> None:
    _register_user(auth_client)

    response = auth_client.post("/api/adrs", json={"title": "My First ADR"})

    assert response.status_code == 201
    body = response.json()
    assert "id" in body

    get_response = auth_client.get(f"/api/adrs/{body['id']}")
    assert get_response.status_code == 200
    adr = get_response.json()
    assert adr["title"] == "My First ADR"
    assert adr["content"] == ADR_STARTER_TEMPLATE
    assert adr["status"] == "draft"


def test_create_adr_without_title_returns_422(auth_client) -> None:
    _register_user(auth_client)

    response = auth_client.post("/api/adrs", json={})

    assert response.status_code == 422


def test_create_adr_with_duplicate_title_returns_409(auth_client) -> None:
    _register_user(auth_client)
    auth_client.post("/api/adrs", json={"title": "Duplicate Title"})

    response = auth_client.post("/api/adrs", json={"title": "Duplicate Title"})

    assert response.status_code == 409
    assert "detail" in response.json()


def test_create_adr_same_title_different_users_succeeds(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "user-a@example.com", "password": "password123"},
    )
    auth_client.post("/api/adrs", json={"title": "Shared Title"})
    auth_client.cookies.clear()

    auth_client.post(
        "/api/auth/register",
        json={"email": "user-b@example.com", "password": "password123"},
    )
    response = auth_client.post("/api/adrs", json={"title": "Shared Title"})

    assert response.status_code == 201


def test_get_adr_returns_created_adr(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client, "Get Me ADR")

    response = auth_client.get(f"/api/adrs/{adr_id}")

    assert response.status_code == 200
    adr = response.json()
    assert adr["id"] == str(adr_id)
    assert adr["title"] == "Get Me ADR"
    assert adr["content"] == ADR_STARTER_TEMPLATE


def test_patch_adr_updates_title_and_content(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    response = auth_client.patch(
        f"/api/adrs/{adr_id}",
        json={"title": "Updated Title", "content": "## Updated content"},
    )

    assert response.status_code == 200
    adr = response.json()
    assert adr["title"] == "Updated Title"
    assert adr["content"] == "## Updated content"


def test_patch_adr_with_duplicate_title_returns_409(auth_client) -> None:
    _register_user(auth_client)
    _create_adr(auth_client, "Existing Title")
    adr_id = _create_adr(auth_client, "Another ADR")

    response = auth_client.patch(
        f"/api/adrs/{adr_id}",
        json={"title": "Existing Title"},
    )

    assert response.status_code == 409


def test_beacon_save_updates_content_and_returns_204(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    response = auth_client.post(
        f"/api/adrs/{adr_id}/save",
        json={"content": "Beacon saved content"},
    )

    assert response.status_code == 204
    assert response.content == b""


def test_get_after_patch_returns_updated_content(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    auth_client.patch(
        f"/api/adrs/{adr_id}",
        json={"content": "Persisted update"},
    )

    response = auth_client.get(f"/api/adrs/{adr_id}")

    assert response.status_code == 200
    assert response.json()["content"] == "Persisted update"


def test_search_by_title_returns_matching_adrs(auth_client) -> None:
    _register_user(auth_client)
    _create_adr(auth_client, "Authentication Strategy")
    _create_adr(auth_client, "Database Selection")

    response = auth_client.get("/api/adrs/search", params={"q": "Auth"})

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["title"] == "Authentication Strategy"


def test_search_by_title_returns_empty_for_non_matching_query(auth_client) -> None:
    _register_user(auth_client)
    _create_adr(auth_client, "Some ADR")

    response = auth_client.get("/api/adrs/search", params={"q": "nonexistent"})

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_does_not_return_other_users_adrs(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    auth_client.post("/api/adrs", json={"title": "Owner Only ADR"})
    auth_client.cookies.clear()

    auth_client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    response = auth_client.get("/api/adrs/search", params={"q": "Owner"})

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_unauthenticated_create_returns_401(auth_client) -> None:
    response = auth_client.post("/api/adrs", json={"title": "No Auth"})

    assert response.status_code == 401


def test_unauthenticated_get_returns_401(auth_client) -> None:
    response = auth_client.get(f"/api/adrs/{UUID(int=0)}")

    assert response.status_code == 401


def test_accessing_another_users_adr_returns_404(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    create_response = auth_client.post("/api/adrs", json={"title": "Private ADR"})
    adr_id = create_response.json()["id"]
    auth_client.cookies.clear()

    auth_client.post(
        "/api/auth/register",
        json={"email": "intruder@example.com", "password": "password123"},
    )
    response = auth_client.get(f"/api/adrs/{adr_id}")

    assert response.status_code == 404


def test_patch_in_review_status_returns_error(auth_client, db_engine) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    with db_engine.begin() as connection:
        connection.execute(
            text("UPDATE adrs SET status = 'in_review' WHERE id = :id"),
            {"id": str(adr_id)},
        )

    response = auth_client.patch(
        f"/api/adrs/{adr_id}",
        json={"content": "Should not save"},
    )

    assert response.status_code == 400
    assert "review" in response.json()["detail"].lower()
