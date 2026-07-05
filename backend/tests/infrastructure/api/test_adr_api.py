"""ADR API integration tests."""

import time
from typing import Any, cast
from uuid import UUID

import pytest
from domain.adr.template import ADR_STARTER_TEMPLATE
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.infrastructure.api.conftest import (
    clear_bearer_auth,
    register_and_get_token,
    set_bearer_auth,
)


def _register_user(client: TestClient, email: str = "adr-user@example.com") -> str:
    token = register_and_get_token(client, email)
    set_bearer_auth(client, token)
    return token


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
    assert response.json()["kind"] == "adr_title_already_exists"


def test_create_adr_same_title_different_users_succeeds(auth_client) -> None:
    token_a = register_and_get_token(auth_client, "user-a@example.com")
    set_bearer_auth(auth_client, token_a)
    auth_client.post("/api/adrs", json={"title": "Shared Title"})
    clear_bearer_auth(auth_client)

    token_b = register_and_get_token(auth_client, "user-b@example.com")
    set_bearer_auth(auth_client, token_b)
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
    token_owner = register_and_get_token(auth_client, "owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    auth_client.post("/api/adrs", json={"title": "Owner Only ADR"})
    clear_bearer_auth(auth_client)

    token_other = register_and_get_token(auth_client, "other@example.com")
    set_bearer_auth(auth_client, token_other)
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
    token_owner = register_and_get_token(auth_client, "owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    create_response = auth_client.post("/api/adrs", json={"title": "Private ADR"})
    adr_id = create_response.json()["id"]
    clear_bearer_auth(auth_client)

    token_intruder = register_and_get_token(auth_client, "intruder@example.com")
    set_bearer_auth(auth_client, token_intruder)
    response = auth_client.get(f"/api/adrs/{adr_id}")

    assert response.status_code == 404


def test_patch_returns_404_for_other_users_adr(auth_client) -> None:
    token_owner = register_and_get_token(auth_client, "patch-owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    create_response = auth_client.post(
        "/api/adrs",
        json={"title": "Owner Title"},
    )
    adr_id = create_response.json()["id"]
    auth_client.patch(
        f"/api/adrs/{adr_id}",
        json={"content": "Owner content"},
    )
    clear_bearer_auth(auth_client)

    token_intruder = register_and_get_token(auth_client, "patch-intruder@example.com")
    set_bearer_auth(auth_client, token_intruder)
    response = auth_client.patch(
        f"/api/adrs/{adr_id}",
        json={"content": "stolen", "title": "Hijacked"},
    )

    assert response.status_code == 404

    set_bearer_auth(auth_client, token_owner)
    owner_adr = auth_client.get(f"/api/adrs/{adr_id}").json()
    assert owner_adr["title"] == "Owner Title"
    assert owner_adr["content"] == "Owner content"


def test_beacon_save_returns_404_for_other_users_adr(auth_client) -> None:
    token_owner = register_and_get_token(auth_client, "save-owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    create_response = auth_client.post(
        "/api/adrs",
        json={"title": "Save Owner ADR"},
    )
    adr_id = create_response.json()["id"]
    auth_client.patch(
        f"/api/adrs/{adr_id}",
        json={"content": "Owner saved content"},
    )
    clear_bearer_auth(auth_client)

    token_intruder = register_and_get_token(auth_client, "save-intruder@example.com")
    set_bearer_auth(auth_client, token_intruder)
    response = auth_client.post(
        f"/api/adrs/{adr_id}/save",
        json={"content": "intruder content"},
    )

    assert response.status_code == 404

    set_bearer_auth(auth_client, token_owner)
    owner_adr = auth_client.get(f"/api/adrs/{adr_id}").json()
    assert owner_adr["content"] == "Owner saved content"


def test_retry_review_returns_404_for_other_users_adr(auth_client) -> None:
    token_owner = register_and_get_token(auth_client, "retry-owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    adr_id = _create_adr(auth_client, "Retry Owner ADR")
    clear_bearer_auth(auth_client)

    token_intruder = register_and_get_token(auth_client, "retry-intruder@example.com")
    set_bearer_auth(auth_client, token_intruder)
    response = auth_client.post(f"/api/adrs/{adr_id}/retry-review")

    assert response.status_code == 404

    set_bearer_auth(auth_client, token_owner)
    owner_adr = auth_client.get(f"/api/adrs/{adr_id}").json()
    assert owner_adr["status"] == "draft"


def test_patch_in_review_status_returns_error(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)
    auth_client.post(f"/api/adrs/{adr_id}/submit-review")

    response = auth_client.patch(
        f"/api/adrs/{adr_id}",
        json={"content": "Should not save"},
    )

    assert response.status_code == 400
    assert response.json()["kind"] == "adr_edit_while_in_review"
    assert "review" in response.json()["message"].lower()


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
    token_owner = register_and_get_token(auth_client, "owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    auth_client.post("/api/adrs", json={"title": "Owner Only ADR"})
    clear_bearer_auth(auth_client)

    token_other = register_and_get_token(auth_client, "other@example.com")
    set_bearer_auth(auth_client, token_other)
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


def test_get_adr_includes_section_ratings_after_review(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    auth_client.post(f"/api/adrs/{adr_id}/submit-review")
    _wait_for_review_status(auth_client, adr_id, expected="after_review")

    adr = auth_client.get(f"/api/adrs/{adr_id}").json()
    assert adr["section_ratings"] is not None
    assert len(adr["section_ratings"]) == 5
    rated_sections = {rating["section"] for rating in adr["section_ratings"]}
    assert rated_sections == {
        "Context",
        "Options",
        "Decision",
        "Status",
        "Consequences",
    }
    for rating in adr["section_ratings"]:
        assert "score" in rating
        assert 0 <= rating["score"] <= 5
        assert "feedback" in rating


def test_submit_review_rejects_non_draft_status(auth_client) -> None:
    adr_id = _seed_after_review_adr(auth_client)

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
    token_owner = register_and_get_token(auth_client, "owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    adr_id = _create_adr(auth_client, "Private ADR")
    clear_bearer_auth(auth_client)

    token_intruder = register_and_get_token(auth_client, "intruder@example.com")
    set_bearer_auth(auth_client, token_intruder)
    response = auth_client.get(f"/api/adrs/{adr_id}/review-status")

    assert response.status_code == 404


def test_submit_review_returns_404_for_other_users_adr(auth_client) -> None:
    token_owner = register_and_get_token(auth_client, "owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    adr_id = _create_adr(auth_client, "Private ADR")
    clear_bearer_auth(auth_client)

    token_intruder = register_and_get_token(auth_client, "intruder@example.com")
    set_bearer_auth(auth_client, token_intruder)
    response = auth_client.post(f"/api/adrs/{adr_id}/submit-review")

    assert response.status_code == 404


def test_invalid_review_surfaces_review_error(
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

    class InvalidReviewService:
        async def review_adr(
            self,
            markdown: str,
            *,
            validation_feedback: tuple[str, ...] = (),
        ):
            from datetime import UTC, datetime

            from domain.adr.value_objects import ReviewResult

            del markdown, validation_feedback
            return ReviewResult(
                annotations=(),
                reviewed_at=datetime.now(UTC),
                section_ratings=(),
            )

    monkeypatch.setattr(
        "infrastructure.bootstrap.build_adr_review_service",
        lambda _settings: InvalidReviewService(),
    )
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
        llm_provider="fake",
    )
    with TestClient(create_app(settings=settings)) as client:
        _stop_event_worker(client)
        token = register_and_get_token(client, "invalid-review@example.com")
        set_bearer_auth(client, token)
        adr_id = _create_adr(client, "Invalid Review ADR")
        client.post(f"/api/adrs/{adr_id}/submit-review")
        _drain_event_bus(client)

        completed = client.get(f"/api/adrs/{adr_id}/review-status").json()
        assert completed["status"] == "after_review"
        assert completed["review_error"] is None
        assert completed["reviewed_at"] is not None

        adr = client.get(f"/api/adrs/{adr_id}").json()
        assert adr["status"] == "after_review"
        assert adr["review_error"] is None
        assert adr["section_ratings"] in (None, [])


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


class _CountingValidReviewService:
    def __init__(self) -> None:
        self.calls = 0

    async def review_adr(
        self,
        markdown: str,
        *,
        validation_feedback: tuple[str, ...] = (),
    ):
        from datetime import UTC, datetime

        from domain.adr.required_sections import SectionName
        from domain.adr.static_review import synthesize_static_review
        from domain.adr.value_objects import ReviewResult, SectionRating

        del validation_feedback
        self.calls += 1
        static_annotations, static_ratings = synthesize_static_review(markdown)
        gap_sections = {rating.section for rating in static_ratings}
        llm_ratings = tuple(
            SectionRating(section=section, score=3, feedback="Adequate content.")
            for section in SectionName
            if section not in gap_sections
        )
        return ReviewResult(
            annotations=static_annotations,
            reviewed_at=datetime.now(UTC),
            reviewed_content=markdown,
            section_ratings=(*static_ratings, *llm_ratings),
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

    review_service = _CountingValidReviewService()
    monkeypatch.setattr(
        "infrastructure.bootstrap.build_adr_review_service",
        lambda _settings: review_service,
    )
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
        llm_provider="fake",
    )
    with TestClient(create_app(settings=settings)) as client:
        _stop_event_worker(client)
        token = register_and_get_token(client, "replay@example.com")
        set_bearer_auth(client, token)
        adr_id = _create_adr(client, "Replay ADR")
        response = client.post(f"/api/adrs/{adr_id}/submit-review")
        assert response.status_code == 202

        status = client.get(f"/api/adrs/{adr_id}/review-status").json()
        assert status["status"] == "in_review"
        assert review_service.calls == 0

        _drain_event_bus(client)

        assert review_service.calls == 1
        completed = client.get(f"/api/adrs/{adr_id}/review-status").json()
        assert completed["status"] == "after_review"
        assert completed["review_error"] is None


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
        llm_provider="fake",
    )
    with TestClient(create_app(settings=settings)) as client:
        _stop_event_worker(client)
        token = register_and_get_token(client, "idempotent@example.com")
        set_bearer_auth(client, token)
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


def _seed_after_review_adr(auth_client) -> UUID:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)
    auth_client.post(f"/api/adrs/{adr_id}/submit-review")
    _wait_for_review_status(auth_client, adr_id, expected="after_review")
    return adr_id


def test_publish_moves_after_review_to_proposed(auth_client) -> None:
    adr_id = _seed_after_review_adr(auth_client)

    response = auth_client.post(f"/api/adrs/{adr_id}/publish")

    assert response.status_code == 204
    assert response.content == b""

    adr = auth_client.get(f"/api/adrs/{adr_id}").json()
    assert adr["status"] == "proposed"
    assert adr["review_annotations"] is not None


def test_publish_rejects_non_after_review_status(auth_client, db_engine) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    response = auth_client.post(f"/api/adrs/{adr_id}/publish")

    assert response.status_code == 400
    assert response.json()["kind"] == "adr_invalid_publish_status"
    assert "after_review" in response.json()["message"]


def test_domain_error_handler_returns_kind(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    response = auth_client.post(f"/api/adrs/{adr_id}/retry-review")

    assert response.status_code == 400
    body = response.json()
    assert body["kind"] == "adr_invalid_retry_status"
    assert "review_failed" in body["message"]


def test_retry_review_from_review_failed_returns_202(
    postgres_url: str,
    db_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    from domain.errors import RetryableInternalError
    from infrastructure.bootstrap import create_app
    from infrastructure.config import Settings

    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    class FailingReviewService:
        async def review_adr(
            self,
            markdown: str,
            *,
            validation_feedback: tuple[str, ...] = (),
        ):
            del markdown, validation_feedback
            raise RetryableInternalError("LLM provider unavailable")

    monkeypatch.setattr(
        "infrastructure.bootstrap.build_adr_review_service",
        lambda _settings: FailingReviewService(),
    )
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
        llm_provider="fake",
    )
    with TestClient(create_app(settings=settings)) as client:
        _stop_event_worker(client)
        token = register_and_get_token(client, "retry-user@example.com")
        set_bearer_auth(client, token)
        adr_id = _create_adr(client, "Retry Review ADR")
        client.post(f"/api/adrs/{adr_id}/submit-review")
        _drain_event_bus(client)

        failed = client.get(f"/api/adrs/{adr_id}").json()
        assert failed["status"] == "review_failed"
        assert failed["review_error"] is not None
        assert failed["review_error"]["kind"] == "retryable_internal_error"

        response = client.post(f"/api/adrs/{adr_id}/retry-review")
        assert response.status_code == 202
        assert response.content == b""

        retried = client.get(f"/api/adrs/{adr_id}").json()
        assert retried["status"] == "in_review"
        assert retried["review_error"] is None


def test_retry_review_from_draft_returns_400(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    response = auth_client.post(f"/api/adrs/{adr_id}/retry-review")

    assert response.status_code == 400
    body = response.json()
    assert body["kind"] == "adr_invalid_retry_status"


def test_retry_review_returns_404_for_missing_adr(auth_client) -> None:
    _register_user(auth_client)

    response = auth_client.post(f"/api/adrs/{UUID(int=0)}/retry-review")

    assert response.status_code == 404


def test_unauthenticated_retry_review_returns_401(auth_client) -> None:
    response = auth_client.post(f"/api/adrs/{UUID(int=0)}/retry-review")

    assert response.status_code == 401


def test_publish_returns_404_for_missing_adr(auth_client) -> None:
    _register_user(auth_client)

    response = auth_client.post(f"/api/adrs/{UUID(int=0)}/publish")

    assert response.status_code == 404


def test_unauthenticated_publish_returns_401(auth_client) -> None:
    response = auth_client.post(f"/api/adrs/{UUID(int=0)}/publish")

    assert response.status_code == 401


def test_publish_returns_404_for_other_users_adr(auth_client) -> None:
    token_owner = register_and_get_token(auth_client, "publish-owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    adr_id = _seed_after_review_adr(auth_client)
    clear_bearer_auth(auth_client)

    token_intruder = register_and_get_token(auth_client, "publish-intruder@example.com")
    set_bearer_auth(auth_client, token_intruder)
    response = auth_client.post(f"/api/adrs/{adr_id}/publish")

    assert response.status_code == 404


def test_delete_adr_returns_204_and_excludes_from_list(auth_client, db_engine) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client, "Delete Me ADR")
    _create_adr(auth_client, "Keep Me ADR")

    response = auth_client.delete(f"/api/adrs/{adr_id}")

    assert response.status_code == 204
    assert response.content == b""

    list_response = auth_client.get("/api/adrs")
    assert list_response.status_code == 200
    titles = [adr["title"] for adr in list_response.json()["results"]]
    assert "Delete Me ADR" not in titles
    assert "Keep Me ADR" in titles

    get_response = auth_client.get(f"/api/adrs/{adr_id}")
    assert get_response.status_code == 404

    with db_engine.begin() as connection:
        row = connection.execute(
            text("SELECT is_deleted, status FROM adrs WHERE id = :id"),
            {"id": adr_id},
        ).one()
        assert row.is_deleted is True
        assert row.status == "draft"


def test_delete_adr_twice_returns_400_already_deleted(auth_client) -> None:
    _register_user(auth_client)
    adr_id = _create_adr(auth_client)

    first = auth_client.delete(f"/api/adrs/{adr_id}")
    assert first.status_code == 204

    second = auth_client.delete(f"/api/adrs/{adr_id}")
    assert second.status_code == 400
    assert second.json()["kind"] == "adr_already_deleted"


def test_delete_adr_returns_404_for_missing_adr(auth_client) -> None:
    _register_user(auth_client)

    response = auth_client.delete(f"/api/adrs/{UUID(int=0)}")

    assert response.status_code == 404


def test_unauthenticated_delete_returns_401(auth_client) -> None:
    response = auth_client.delete(f"/api/adrs/{UUID(int=0)}")

    assert response.status_code == 401


def test_delete_adr_returns_404_for_other_users_adr(auth_client) -> None:
    token_owner = register_and_get_token(auth_client, "delete-owner@example.com")
    set_bearer_auth(auth_client, token_owner)
    adr_id = _create_adr(auth_client)
    clear_bearer_auth(auth_client)

    token_intruder = register_and_get_token(auth_client, "delete-intruder@example.com")
    set_bearer_auth(auth_client, token_intruder)
    response = auth_client.delete(f"/api/adrs/{adr_id}")

    assert response.status_code == 404
