"""PublishAdr command handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.commands.publish_adr import PublishAdrCommand, PublishAdrCommandHandler
from domain.adr import ADRPublished
from domain.adr.events import ADRSubmittedForReview, AIReviewCompleted
from domain.adr.value_objects import (
    AdrContent,
    AdrId,
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from domain.errors import AdrInvalidPublishStatus, AdrNotFound
from domain.user.value_objects import UserId
from tests.application.commands.fakes import (
    FakeEventStore,
    FakeUnitOfWorkFactory,
    adr_created_stream,
)

_REVIEWED_AT = datetime(2026, 6, 17, 11, 0, tzinfo=UTC)


def _after_review_stream(
    *, adr_id, user_id, content: str = "## Context\n\nReviewed body"
):
    submitted_at = datetime(2026, 6, 17, 10, 30, tzinfo=UTC)
    body = AdrContent(content)
    review_result = ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing section",
            ),
        ),
        reviewed_at=_REVIEWED_AT,
    )
    return adr_created_stream(
        adr_id=adr_id,
        user_id=user_id,
        content=content,
        extra_events=[
            ADRSubmittedForReview(
                adr_id=AdrId(adr_id),
                user_id=UserId(user_id),
                content=body,
                occurred_at=submitted_at,
            ),
            AIReviewCompleted(
                adr_id=AdrId(adr_id),
                review_result=review_result,
                occurred_at=_REVIEWED_AT,
            ),
        ],
    )


def test_publish_adr_emits_event_marks_proposed_and_marks_processed() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    stream = _after_review_stream(adr_id=adr_id, user_id=user_id)
    event_store = FakeEventStore(streams={(adr_id, "adr"): stream})
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = PublishAdrCommandHandler(uow_factory)

    asyncio.run(handler.handle(PublishAdrCommand(adr_id=adr_id, user_id=user_id)))

    uow = uow_factory.unit_of_works[0]
    assert uow.locked_aggregates == [adr_id]
    assert event_store.load_stream_calls == [(adr_id, "adr")]
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ADRPublished)
    assert event.adr_id.value == adr_id
    assert not hasattr(event, "user_id")
    assert not hasattr(event, "content")

    assert len(uow.adr_projection.marked_proposed) == 1
    marked_id, marked_at = uow.adr_projection.marked_proposed[0]
    assert marked_id == adr_id
    assert marked_at == event.occurred_at

    assert len(uow.event_store.marked_processed) == 1
    processed_id, processed_at = uow.event_store.marked_processed[0]
    assert processed_at == event.occurred_at
    assert processed_id is not None


def test_publish_adr_raises_not_found_when_stream_empty() -> None:
    handler = PublishAdrCommandHandler(FakeUnitOfWorkFactory())

    with pytest.raises(AdrNotFound):
        asyncio.run(handler.handle(PublishAdrCommand(adr_id=uuid4(), user_id=uuid4())))


@pytest.mark.parametrize(
    "status_stream",
    [
        "draft_only",
        "in_review",
    ],
)
def test_publish_adr_rejects_non_after_review_status(status_stream: str) -> None:
    user_id = uuid4()
    adr_id = uuid4()
    extra_events = []
    if status_stream == "in_review":
        extra_events = [
            ADRSubmittedForReview(
                adr_id=AdrId(adr_id),
                user_id=UserId(user_id),
                content=AdrContent("## Context"),
                occurred_at=datetime(2026, 6, 17, 10, 0, tzinfo=UTC),
            )
        ]
    stream = adr_created_stream(
        adr_id=adr_id,
        user_id=user_id,
        extra_events=extra_events,
    )
    handler = PublishAdrCommandHandler(
        FakeUnitOfWorkFactory(
            event_store=FakeEventStore(streams={(adr_id, "adr"): stream})
        )
    )

    with pytest.raises(AdrInvalidPublishStatus, match="after_review"):
        asyncio.run(handler.handle(PublishAdrCommand(adr_id=adr_id, user_id=user_id)))
