"""SubmitAdrForReview command handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.commands.submit_adr_for_review import (
    SubmitAdrForReviewCommand,
    SubmitAdrForReviewCommandHandler,
)
from domain.adr import ADRSubmittedForReview
from domain.adr.events import ADRSubmittedForReview as SubmittedEvent
from domain.adr.value_objects import AdrContent, AdrId
from domain.errors import AdrInvalidSubmitStatus, AdrNotFound
from domain.user.value_objects import UserId
from tests.application.commands.fakes import (
    FakeEventStore,
    FakeUnitOfWorkFactory,
    adr_created_stream,
)


def test_submit_adr_for_review_emits_event_marks_in_review_and_returns_stored_event() -> (
    None
):
    user_id = uuid4()
    adr_id = uuid4()
    content = "## Context\n\nReady for review"
    stream = adr_created_stream(adr_id=adr_id, user_id=user_id, content=content)
    event_store = FakeEventStore(streams={(adr_id, "adr"): stream})
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = SubmitAdrForReviewCommandHandler(uow_factory)

    result = asyncio.run(
        handler.handle(SubmitAdrForReviewCommand(adr_id=adr_id, user_id=user_id))
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


def test_submit_adr_for_review_raises_not_found_when_stream_empty() -> None:
    handler = SubmitAdrForReviewCommandHandler(FakeUnitOfWorkFactory())

    with pytest.raises(AdrNotFound):
        asyncio.run(
            handler.handle(SubmitAdrForReviewCommand(adr_id=uuid4(), user_id=uuid4()))
        )


def test_submit_adr_for_review_rejects_non_draft_status() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    when = datetime(2026, 6, 17, 10, 0, tzinfo=UTC)
    submitted = SubmittedEvent(
        adr_id=AdrId(adr_id),
        user_id=UserId(user_id),
        content=AdrContent("## Context\n\nDraft body"),
        occurred_at=when,
    )
    stream = adr_created_stream(
        adr_id=adr_id,
        user_id=user_id,
        content="## Context\n\nDraft body",
        extra_events=[submitted],
    )
    handler = SubmitAdrForReviewCommandHandler(
        FakeUnitOfWorkFactory(
            event_store=FakeEventStore(streams={(adr_id, "adr"): stream})
        )
    )

    with pytest.raises(AdrInvalidSubmitStatus):
        asyncio.run(
            handler.handle(SubmitAdrForReviewCommand(adr_id=adr_id, user_id=user_id))
        )
