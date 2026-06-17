"""ADR API integration tests."""

import time
from typing import Any, cast
from uuid import UUID

import pytest
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


def test_create_adr_with_blank_title_returns_422(auth_client) -> None:
    _register_user(auth_client)

    response = auth_client.post("/api/adrs", json={"title": "   "})

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


def test_patch_adr_with_blank_title_returns_422(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    response = auth_client.patch(f"/api/adrs/{adr_id}", json={"title": "   "})

    assert response.status_code == 422


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


def test_list_adrs_returns_empty_for_new_user(auth_client) -> None:
    _register_user(auth_client)

    response = auth_client.get("/api/adrs")

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_list_adrs_returns_owned_adrs_sorted_by_updated_at_desc(auth_client) -> None:
    _register_user(auth_client)
    first_id = _create_adr(auth_client, "First ADR")
    second_id = _create_adr(auth_client, "Second ADR")

    auth_client.patch(
        f"/api/adrs/{first_id}",
        json={"content": "Updated first"},
    )

    response = auth_client.get("/api/adrs")

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert results[0]["id"] == str(first_id)
    assert results[1]["id"] == str(second_id)
    assert results[0]["title"] == "First ADR"
    assert results[0]["status"] == "draft"
    assert "updated_at" in results[0]


def test_list_adrs_respects_limit_and_offset(auth_client) -> None:
    _register_user(auth_client)
    _create_adr(auth_client, "ADR One")
    _create_adr(auth_client, "ADR Two")
    _create_adr(auth_client, "ADR Three")

    full_response = auth_client.get("/api/adrs")
    response = auth_client.get("/api/adrs", params={"limit": 1, "offset": 1})

    assert full_response.status_code == 200
    assert response.status_code == 200
    full_results = full_response.json()["results"]
    results = response.json()["results"]
    assert len(full_results) == 3
    assert len(results) == 1
    assert results[0]["id"] == full_results[1]["id"]


def test_list_adrs_does_not_return_other_users_adrs(auth_client) -> None:
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
    response = auth_client.get("/api/adrs")

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_unauthenticated_list_returns_401(auth_client) -> None:
    response = auth_client.get("/api/adrs")

    assert response.status_code == 401


def _portal_call(client: TestClient, fn, *args):
    portal = client.portal
    assert portal is not None
    return portal.call(fn, *args)


def _stop_event_worker(client: TestClient) -> None:
    app = cast(Any, client.app)
    event_bus = getattr(app.state, "event_bus", None)
    if event_bus is not None:
        _portal_call(client, event_bus.stop_worker)


def _drain_event_bus(client: TestClient) -> int:
    app = cast(Any, client.app)
    drain = getattr(app.state, "drain_event_bus_once", None)
    assert drain is not None
    return _portal_call(client, drain)


def _wait_for_review_status(
    auth_client, adr_id: UUID, *, expected: str, timeout: float = 3.0
) -> dict:
    deadline = time.monotonic() + timeout
    drain_event_bus_once = getattr(
        auth_client.app.state,
        "drain_event_bus_once",
        None,
    )
    event_bus = getattr(auth_client.app.state, "event_bus", None)
    if event_bus is not None:
        auth_client.portal.call(event_bus.stop_worker)
    while time.monotonic() < deadline:
        if drain_event_bus_once is not None:
            auth_client.portal.call(drain_event_bus_once)
        response = auth_client.get(f"/api/adrs/{adr_id}/review-status")
        assert response.status_code == 200
        body = response.json()
        if body["status"] == expected:
            return body
        time.sleep(0.05)
    msg = f"Timed out waiting for review status {expected}"
    raise AssertionError(msg)


def test_submit_review_moves_draft_to_in_review_and_completes(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    response = auth_client.post(f"/api/adrs/{adr_id}/submit-review")

    assert response.status_code == 202
    assert response.content == b""

    in_review = auth_client.get(f"/api/adrs/{adr_id}/review-status").json()
    assert in_review["status"] == "in_review"
    assert in_review["review_error"] is None

    completed = _wait_for_review_status(auth_client, adr_id, expected="after_review")
    assert completed["reviewed_at"] is not None
    assert completed["annotation_counts"] is not None
    assert completed["annotation_counts"].get("missing_section", 0) >= 1

    adr = auth_client.get(f"/api/adrs/{adr_id}").json()
    assert adr["status"] == "after_review"
    assert adr["review_annotations"] is not None


def test_submit_review_rejects_non_draft_status(auth_client, db_engine) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    with db_engine.begin() as connection:
        connection.execute(
            text("UPDATE adrs SET status = 'after_review' WHERE id = :id"),
            {"id": str(adr_id)},
        )

    response = auth_client.post(f"/api/adrs/{adr_id}/submit-review")

    assert response.status_code == 400


def test_submit_review_returns_404_for_missing_adr(auth_client) -> None:
    _register_user(auth_client)

    response = auth_client.post(f"/api/adrs/{UUID(int=0)}/submit-review")

    assert response.status_code == 404


def test_unauthenticated_submit_review_returns_401(auth_client) -> None:
    response = auth_client.post(f"/api/adrs/{UUID(int=0)}/submit-review")

    assert response.status_code == 401


def test_review_status_returns_404_for_other_users_adr(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    adr_id = _create_adr(auth_client, "Private ADR")
    auth_client.cookies.clear()

    auth_client.post(
        "/api/auth/register",
        json={"email": "intruder@example.com", "password": "password123"},
    )
    response = auth_client.get(f"/api/adrs/{adr_id}/review-status")

    assert response.status_code == 404


def test_submit_review_returns_404_for_other_users_adr(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    adr_id = _create_adr(auth_client, "Private ADR")
    auth_client.cookies.clear()

    auth_client.post(
        "/api/auth/register",
        json={"email": "intruder@example.com", "password": "password123"},
    )
    response = auth_client.post(f"/api/adrs/{adr_id}/submit-review")

    assert response.status_code == 404


def test_review_status_exposes_failure_metadata_after_invalid_review(
    postgres_url: str,
    db_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from domain.adr.value_objects import ReviewResult
    from fastapi.testclient import TestClient

    from infrastructure.bootstrap import create_app
    from infrastructure.config import Settings

    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    class InvalidReviewer:
        async def review(self, markdown: str) -> ReviewResult:
            return ReviewResult(
                annotations=(),
                reviewed_at=datetime.now(UTC),
            )

    monkeypatch.setattr(
        "infrastructure.bootstrap.build_llm_reviewer",
        lambda _settings: InvalidReviewer(),
    )
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
        cookie_secure=False,
        cookie_path="/api",
        llm_provider="fake",
    )
    with TestClient(create_app(settings=settings)) as client:
        _stop_event_worker(client)
        client.post(
            "/api/auth/register",
            json={"email": "invalid-review@example.com", "password": "password123"},
        )
        adr_id = _create_adr(client, "Invalid Review ADR")
        client.post(f"/api/adrs/{adr_id}/submit-review")
        _drain_event_bus(client)

        failed = client.get(f"/api/adrs/{adr_id}/review-status").json()
        assert failed["status"] == "in_review"
        assert failed["review_error"] is not None
        assert failed["review_error"]["code"] == "validation_failed"
        assert failed["review_error"]["message"]

        adr = client.get(f"/api/adrs/{adr_id}").json()
        assert adr["status"] == "in_review"
        assert adr["review_error"] is not None


def test_submit_review_returns_202_before_review_work_completes(auth_client) -> None:
    _stop_event_worker(auth_client)

    _register_user(auth_client, email="fast-submit@example.com")
    adr_id = _create_adr(auth_client, "Fast Submit ADR")

    response = auth_client.post(f"/api/adrs/{adr_id}/submit-review")
    assert response.status_code == 202

    in_review = auth_client.get(f"/api/adrs/{adr_id}/review-status").json()
    assert in_review["status"] == "in_review"
    assert in_review["review_error"] is None
    assert in_review["reviewed_at"] is None


class _CountingInvalidReviewer:
    def __init__(self) -> None:
        self.calls = 0

    async def review(self, markdown: str):
        from datetime import UTC, datetime

        from domain.adr.value_objects import ReviewResult

        self.calls += 1
        return ReviewResult(
            annotations=(),
            reviewed_at=datetime.now(UTC),
        )


def test_replay_processes_unprocessed_submit_event(
    postgres_url: str,
    db_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    from infrastructure.bootstrap import create_app
    from infrastructure.config import Settings

    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    reviewer = _CountingInvalidReviewer()
    monkeypatch.setattr(
        "infrastructure.bootstrap.build_llm_reviewer",
        lambda _settings: reviewer,
    )
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
        cookie_secure=False,
        cookie_path="/api",
        llm_provider="fake",
    )
    with TestClient(create_app(settings=settings)) as client:
        _stop_event_worker(client)
        client.post(
            "/api/auth/register",
            json={"email": "replay@example.com", "password": "password123"},
        )
        adr_id = _create_adr(client, "Replay ADR")
        response = client.post(f"/api/adrs/{adr_id}/submit-review")
        assert response.status_code == 202

        status = client.get(f"/api/adrs/{adr_id}/review-status").json()
        assert status["status"] == "in_review"
        assert reviewer.calls == 0

        _drain_event_bus(client)

        assert reviewer.calls == 2
        failed = client.get(f"/api/adrs/{adr_id}/review-status").json()
        assert failed["status"] == "in_review"
        assert failed["review_error"] is not None


def test_replay_does_not_duplicate_completed_review(
    postgres_url: str,
    db_engine,
) -> None:
    from fastapi.testclient import TestClient

    from infrastructure.bootstrap import create_app
    from infrastructure.config import Settings

    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
        cookie_secure=False,
        cookie_path="/api",
        llm_provider="fake",
    )
    with TestClient(create_app(settings=settings)) as client:
        _stop_event_worker(client)
        client.post(
            "/api/auth/register",
            json={"email": "idempotent@example.com", "password": "password123"},
        )
        adr_id = _create_adr(client, "Idempotent ADR")
        client.post(f"/api/adrs/{adr_id}/submit-review")
        _drain_event_bus(client)

        completed = client.get(f"/api/adrs/{adr_id}/review-status").json()
        assert completed["status"] == "after_review"

        with db_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE events SET processed_at = NULL "
                    "WHERE event_type = 'ADRSubmittedForReview' "
                    "AND aggregate_id = :adr_id"
                ),
                {"adr_id": str(adr_id)},
            )

        _drain_event_bus(client)

        adr = client.get(f"/api/adrs/{adr_id}").json()
        assert adr["status"] == "after_review"
        annotation_count = len(adr["review_annotations"] or [])
        assert annotation_count >= 1

        _drain_event_bus(client)
        adr_after_replay = client.get(f"/api/adrs/{adr_id}").json()
        assert len(adr_after_replay["review_annotations"] or []) == annotation_count
