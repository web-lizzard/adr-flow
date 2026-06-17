"""TaskGroup event bus lifecycle tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from application.ports.event_store import StoredEvent
from domain.adr import ADRSubmittedForReview, AdrContent, AdrId
from domain.user.value_objects import UserId
from infrastructure.messaging.task_group_bus import TaskGroupEventBus


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
