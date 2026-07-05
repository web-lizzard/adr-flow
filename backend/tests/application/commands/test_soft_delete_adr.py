"""SoftDeleteAdr command handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.commands.soft_delete_adr import (
    SoftDeleteAdrCommand,
    SoftDeleteAdrCommandHandler,
)
from domain.adr import ADRSoftDeleted
from domain.errors import AdrAlreadyDeleted, AdrNotFound
from tests.application.commands.fakes import (
    FakeEventStore,
    FakeUnitOfWorkFactory,
    adr_created_stream,
    soft_deleted_stream,
)


def test_soft_delete_adr_emits_event_marks_soft_deleted_and_marks_processed() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    stream = adr_created_stream(adr_id=adr_id, user_id=user_id)
    event_store = FakeEventStore(streams={(adr_id, "adr"): stream})
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = SoftDeleteAdrCommandHandler(uow_factory)

    asyncio.run(handler.handle(SoftDeleteAdrCommand(adr_id=adr_id, user_id=user_id)))

    uow = uow_factory.unit_of_works[0]
    assert uow.locked_aggregates == [adr_id]
    assert event_store.load_stream_calls == [(adr_id, "adr")]
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ADRSoftDeleted)
    assert event.adr_id.value == adr_id

    assert len(uow.adr_projection.marked_soft_deleted) == 1
    marked_id, marked_at = uow.adr_projection.marked_soft_deleted[0]
    assert marked_id == adr_id
    assert marked_at == event.occurred_at

    assert len(uow.event_store.marked_processed) == 1
    processed_id, processed_at = uow.event_store.marked_processed[0]
    assert processed_at == event.occurred_at
    assert processed_id is not None


def test_soft_delete_adr_raises_not_found_when_stream_empty() -> None:
    handler = SoftDeleteAdrCommandHandler(FakeUnitOfWorkFactory())

    with pytest.raises(AdrNotFound):
        asyncio.run(
            handler.handle(SoftDeleteAdrCommand(adr_id=uuid4(), user_id=uuid4()))
        )


def test_soft_delete_adr_raises_already_deleted_when_stream_ends_in_soft_deleted() -> (
    None
):
    user_id = uuid4()
    adr_id = uuid4()
    deleted_at = datetime(2026, 7, 5, 10, 0, tzinfo=UTC)
    stream = soft_deleted_stream(
        adr_id=adr_id,
        user_id=user_id,
        deleted_at=deleted_at,
    )
    handler = SoftDeleteAdrCommandHandler(
        FakeUnitOfWorkFactory(
            event_store=FakeEventStore(streams={(adr_id, "adr"): stream})
        )
    )

    with pytest.raises(AdrAlreadyDeleted):
        asyncio.run(
            handler.handle(SoftDeleteAdrCommand(adr_id=adr_id, user_id=user_id))
        )
