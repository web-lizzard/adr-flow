"""Event dispatcher unit tests."""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.runtime.dispatcher import EventDispatcher
from domain.adr import ADRSubmittedForReview, AdrContent, AdrId
from domain.user.value_objects import UserId


def test_dispatcher_invokes_registered_handler() -> None:
    seen: list[str] = []

    async def capture(stored_event) -> None:
        seen.append(type(stored_event.event).__name__)

    dispatcher = EventDispatcher()
    dispatcher.register(ADRSubmittedForReview, capture)

    adr_id = uuid4()
    occurred_at = datetime(2026, 6, 17, 11, 0, tzinfo=UTC)
    from application.ports.event_store import StoredEvent

    stored_event = StoredEvent(
        id=uuid4(),
        aggregate_type="adr",
        aggregate_id=adr_id,
        event=ADRSubmittedForReview(
            adr_id=AdrId(adr_id),
            user_id=UserId(uuid4()),
            content=AdrContent("## Context\n\nTBD"),
            occurred_at=occurred_at,
        ),
        occurred_at=occurred_at,
    )

    asyncio.run(dispatcher.dispatch(stored_event))

    assert seen == ["ADRSubmittedForReview"]


def test_dispatcher_skips_unknown_event_types(caplog: pytest.LogCaptureFixture) -> None:
    from application.ports.event_store import StoredEvent
    from domain.user.events import UserRegistered
    from domain.user.value_objects import EmailAddress, PasswordHash

    dispatcher = EventDispatcher()
    user_id = uuid4()
    occurred_at = datetime(2026, 6, 17, 11, 0, tzinfo=UTC)
    stored_event = StoredEvent(
        id=uuid4(),
        aggregate_type="user",
        aggregate_id=user_id,
        event=UserRegistered(
            user_id=UserId(user_id),
            email=EmailAddress("unknown@example.com"),
            password_hash=PasswordHash("hash"),
            occurred_at=occurred_at,
        ),
        occurred_at=occurred_at,
    )

    with caplog.at_level(logging.WARNING):
        asyncio.run(dispatcher.dispatch(stored_event))

    assert any("No handler registered" in record.message for record in caplog.records)
