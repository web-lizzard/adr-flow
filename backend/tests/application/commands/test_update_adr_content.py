"""UpdateAdrContent command handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.commands.update_adr_content import (
    UpdateAdrContentCommand,
    UpdateAdrContentCommandHandler,
)
from domain.adr import ADRContentUpdated
from domain.adr.events import ADRSubmittedForReview as SubmittedEvent
from domain.adr.value_objects import AdrContent, AdrId
from domain.errors import AdrEditWhileInReview, AdrNotFound
from domain.user.value_objects import UserId
from tests.application.commands.fakes import (
    FakeEventStore,
    FakeUnitOfWorkFactory,
    adr_created_stream,
)


def test_update_adr_content_emits_event_and_updates_projection() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    stream = adr_created_stream(
        adr_id=adr_id,
        user_id=user_id,
        content="old",
    )
    event_store = FakeEventStore(streams={(adr_id, "adr"): stream})
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = UpdateAdrContentCommandHandler(uow_factory)

    asyncio.run(
        handler.handle(
            UpdateAdrContentCommand(
                adr_id=adr_id,
                user_id=user_id,
                title=None,
                content="## Context\n\nUpdated",
            )
        )
    )

    uow = uow_factory.unit_of_works[0]
    assert uow.locked_aggregates == [adr_id]
    assert event_store.load_stream_calls == [(adr_id, "adr")]
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    event = events[0]
    assert isinstance(event, ADRContentUpdated)
    assert event.content.value == "## Context\n\nUpdated"
    assert event.title is None

    updated = uow.adr_projection.updated[0]
    assert updated.content.value == "## Context\n\nUpdated"
    assert updated.title.value == "My ADR"


def test_update_adr_content_includes_title_on_event_when_title_changes() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    stream = adr_created_stream(
        adr_id=adr_id,
        user_id=user_id,
        title="Original",
    )
    event_store = FakeEventStore(streams={(adr_id, "adr"): stream})
    handler = UpdateAdrContentCommandHandler(
        FakeUnitOfWorkFactory(event_store=event_store)
    )

    asyncio.run(
        handler.handle(
            UpdateAdrContentCommand(
                adr_id=adr_id,
                user_id=user_id,
                title="Renamed",
                content=None,
            )
        )
    )

    event = event_store.appended[0][0][0]
    assert isinstance(event, ADRContentUpdated)
    assert event.title is not None
    assert event.title.value == "Renamed"
    assert event.content.value == "## Context"


def test_update_adr_content_raises_not_found_when_stream_empty() -> None:
    adr_id = uuid4()
    handler = UpdateAdrContentCommandHandler(FakeUnitOfWorkFactory())

    with pytest.raises(AdrNotFound):
        asyncio.run(
            handler.handle(
                UpdateAdrContentCommand(
                    adr_id=adr_id,
                    user_id=uuid4(),
                    title=None,
                    content="new",
                )
            )
        )


def test_update_adr_content_raises_not_found_when_owner_mismatch() -> None:
    adr_id = uuid4()
    owner_id = uuid4()
    stream = adr_created_stream(adr_id=adr_id, user_id=owner_id)
    handler = UpdateAdrContentCommandHandler(
        FakeUnitOfWorkFactory(
            event_store=FakeEventStore(streams={(adr_id, "adr"): stream})
        )
    )

    with pytest.raises(AdrNotFound):
        asyncio.run(
            handler.handle(
                UpdateAdrContentCommand(
                    adr_id=adr_id,
                    user_id=uuid4(),
                    title=None,
                    content="new",
                )
            )
        )


def test_update_adr_content_rejects_in_review_status() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    when = datetime(2026, 6, 16, 11, 0, tzinfo=UTC)
    submitted = SubmittedEvent(
        adr_id=AdrId(adr_id),
        user_id=UserId(user_id),
        content=AdrContent("## Context"),
        occurred_at=when,
    )
    stream = adr_created_stream(
        adr_id=adr_id,
        user_id=user_id,
        extra_events=[submitted],
    )
    handler = UpdateAdrContentCommandHandler(
        FakeUnitOfWorkFactory(
            event_store=FakeEventStore(streams={(adr_id, "adr"): stream})
        )
    )

    with pytest.raises(AdrEditWhileInReview):
        asyncio.run(
            handler.handle(
                UpdateAdrContentCommand(
                    adr_id=adr_id,
                    user_id=user_id,
                    title=None,
                    content="blocked",
                )
            )
        )
