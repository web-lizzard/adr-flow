"""RetryAdrForReview command handler tests."""

import asyncio
from uuid import uuid4

import pytest

from application.commands.retry_adr_for_review import (
    RetryAdrForReviewCommand,
    RetryAdrForReviewCommandHandler,
)
from domain.adr import ADRSubmittedForReview
from domain.errors import AdrInvalidRetryStatus, AdrNotFound
from tests.application.commands.fakes import (
    FakeEventStore,
    FakeUnitOfWorkFactory,
    adr_created_stream,
    review_failed_stream,
)


def test_retry_adr_for_review_emits_event_marks_in_review_and_returns_stored_event() -> (
    None
):
    user_id = uuid4()
    adr_id = uuid4()
    content = "## Context\n\nReady for retry"
    stream = review_failed_stream(adr_id=adr_id, user_id=user_id, content=content)
    event_store = FakeEventStore(streams={(adr_id, "adr"): stream})
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = RetryAdrForReviewCommandHandler(uow_factory)

    result = asyncio.run(
        handler.handle(RetryAdrForReviewCommand(adr_id=adr_id, user_id=user_id))
    )

    uow = uow_factory.unit_of_works[0]
    assert uow.locked_aggregates == [adr_id]
    assert event_store.load_stream_calls == [(adr_id, "adr")]
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ADRSubmittedForReview)
    assert event.content.value == content
    assert event.user_id.value == user_id

    assert len(uow.adr_projection.marked_in_review) == 1
    marked_id, marked_at = uow.adr_projection.marked_in_review[0]
    assert marked_id == adr_id
    assert marked_at == event.occurred_at

    assert result.stored_event.event is event
    assert result.stored_event.aggregate_id == adr_id


def test_retry_adr_for_review_raises_not_found_when_stream_empty() -> None:
    handler = RetryAdrForReviewCommandHandler(FakeUnitOfWorkFactory())

    with pytest.raises(AdrNotFound):
        asyncio.run(
            handler.handle(RetryAdrForReviewCommand(adr_id=uuid4(), user_id=uuid4()))
        )


def test_retry_adr_for_review_rejects_non_review_failed_status() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    stream = adr_created_stream(adr_id=adr_id, user_id=user_id)
    handler = RetryAdrForReviewCommandHandler(
        FakeUnitOfWorkFactory(
            event_store=FakeEventStore(streams={(adr_id, "adr"): stream})
        )
    )

    with pytest.raises(AdrInvalidRetryStatus):
        asyncio.run(
            handler.handle(RetryAdrForReviewCommand(adr_id=adr_id, user_id=user_id))
        )
