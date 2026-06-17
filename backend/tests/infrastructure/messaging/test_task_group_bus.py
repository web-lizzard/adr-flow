"""TaskGroup event bus lifecycle tests."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from application.ports.event_store import StoredEvent
from domain.adr import ADRSubmittedForReview, AdrContent, AdrId
from domain.user.value_objects import UserId
from infrastructure.bootstrap import create_app
from infrastructure.config import Settings
from infrastructure.messaging.task_group_bus import TaskGroupEventBus


def _portal_call(client: TestClient, fn: Any, *args: Any) -> Any:
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


def _stored_event() -> StoredEvent:
    adr_id = uuid4()
    occurred_at = datetime(2026, 6, 17, 11, 0, tzinfo=UTC)
    event = ADRSubmittedForReview(
        adr_id=AdrId(adr_id),
        user_id=UserId(uuid4()),
        content=AdrContent("## Context\n\nTBD"),
        occurred_at=occurred_at,
    )
    return StoredEvent(
        id=uuid4(),
        aggregate_type="adr",
        aggregate_id=adr_id,
        event=event,
        occurred_at=occurred_at,
    )


def test_worker_drain_runs_in_background_until_stopped() -> None:
    started = asyncio.Event()
    finished = asyncio.Event()

    async def slow_drain() -> int:
        started.set()
        await asyncio.sleep(0.05)
        finished.set()
        return 0

    async def run() -> None:
        bus = TaskGroupEventBus()
        bus.start_worker(slow_drain, poll_interval_seconds=10)
        await asyncio.sleep(0)
        assert started.is_set()
        assert not finished.is_set()
        await bus.stop_worker()
        assert finished.is_set()

    asyncio.run(run())


def test_dispatch_now_runs_handler_inline() -> None:
    seen: list[StoredEvent] = []

    async def capture(stored_event: StoredEvent) -> None:
        seen.append(stored_event)

    async def run() -> None:
        stored_event = _stored_event()
        bus = TaskGroupEventBus()
        bus.set_dispatch(capture)
        await bus.dispatch_now(stored_event)
        assert seen == [stored_event]

    asyncio.run(run())


@pytest.fixture()
def review_bus_client(postgres_url: str, db_engine) -> Iterator[TestClient]:
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
        yield client


def test_submit_review_returns_before_worker_processes_event(
    review_bus_client: TestClient,
) -> None:
    review_bus_client.post(
        "/api/auth/register",
        json={"email": "bus-user@example.com", "password": "password123"},
    )
    create_response = review_bus_client.post(
        "/api/adrs",
        json={"title": "Bus Lifecycle ADR"},
    )
    assert create_response.status_code == 201
    adr_id = create_response.json()["id"]

    _stop_event_worker(review_bus_client)

    response = review_bus_client.post(f"/api/adrs/{adr_id}/submit-review")
    assert response.status_code == 202

    status = review_bus_client.get(f"/api/adrs/{adr_id}/review-status").json()
    assert status["status"] == "in_review"
    assert status["reviewed_at"] is None

    drained = _drain_event_bus(review_bus_client)
    assert drained == 1

    completed = review_bus_client.get(f"/api/adrs/{adr_id}/review-status").json()
    assert completed["status"] == "after_review"
    assert completed["reviewed_at"] is not None


def test_worker_continues_after_route_returns_and_shuts_down_cleanly(
    review_bus_client: TestClient,
) -> None:
    app = cast(Any, review_bus_client.app)
    event_bus = getattr(app.state, "event_bus", None)
    assert event_bus is not None

    _stop_event_worker(review_bus_client)

    async def noop_drain() -> int:
        return 0

    _portal_call(review_bus_client, event_bus.start_worker, noop_drain)
    _portal_call(review_bus_client, event_bus.stop_worker)
