"""ADR rehydration from event streams."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.adr.events import (
    ADRContentUpdated,
    ADRCreated,
    ADRPublished,
    ADRSoftDeleted,
    ADRSubmittedForReview,
    AIReviewCompleted,
    AIReviewFailed,
)
from domain.adr.rehydrate import rehydrate_adr
from domain.adr.value_objects import (
    AdrContent,
    AdrId,
    AdrStatus,
    AdrTitle,
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewError,
    ReviewResult,
)
from domain.events import DomainEvent
from domain.user.value_objects import UserId

_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
_LATER = datetime(2026, 6, 18, 13, 0, tzinfo=UTC)
_EVEN_LATER = datetime(2026, 6, 18, 14, 0, tzinfo=UTC)
_FINAL = datetime(2026, 6, 18, 15, 0, tzinfo=UTC)


def _adr_ids() -> tuple[AdrId, UserId]:
    return AdrId(uuid4()), UserId(uuid4())


def test_rehydrate_adr_empty_stream_returns_none() -> None:
    assert rehydrate_adr([]) is None


def test_rehydrate_adr_full_lifecycle_to_proposed() -> None:
    adr_id, user_id = _adr_ids()
    title = AdrTitle("Choose event store")
    content = AdrContent("## Context\n\nTBD")
    updated_content = AdrContent("## Context\n\nUpdated")
    review_result = ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing section",
            ),
        ),
        reviewed_at=_EVEN_LATER,
    )

    events = [
        ADRCreated(
            adr_id=adr_id,
            user_id=user_id,
            title=title,
            content=content,
            occurred_at=_NOW,
        ),
        ADRContentUpdated(
            adr_id=adr_id,
            title=title,
            content=updated_content,
            occurred_at=_LATER,
        ),
        ADRSubmittedForReview(
            adr_id=adr_id,
            user_id=user_id,
            content=updated_content,
            occurred_at=_LATER,
        ),
        AIReviewCompleted(
            adr_id=adr_id,
            review_result=review_result,
            occurred_at=_EVEN_LATER,
        ),
        ADRPublished(
            adr_id=adr_id,
            occurred_at=_FINAL,
        ),
    ]

    adr = rehydrate_adr(events)

    assert adr is not None
    assert adr.status == AdrStatus.PROPOSED
    assert adr.content == updated_content
    assert adr.review_result == review_result
    assert adr.reviewed_at == _EVEN_LATER


def test_rehydrate_adr_content_updated_without_title_keeps_existing_title() -> None:
    adr_id, user_id = _adr_ids()
    title = AdrTitle("Original title")
    content = AdrContent("## Context\n\nTBD")
    updated_content = AdrContent("## Context\n\nUpdated")

    events = [
        ADRCreated(
            adr_id=adr_id,
            user_id=user_id,
            title=title,
            content=content,
            occurred_at=_NOW,
        ),
        ADRContentUpdated(
            adr_id=adr_id,
            content=updated_content,
            occurred_at=_LATER,
        ),
    ]

    adr = rehydrate_adr(events)

    assert adr is not None
    assert adr.title == title
    assert adr.content == updated_content


def test_rehydrate_adr_maps_ai_review_failed() -> None:
    adr_id, user_id = _adr_ids()
    content = AdrContent("## Context\n\nTBD")

    events = [
        ADRCreated(
            adr_id=adr_id,
            user_id=user_id,
            title=AdrTitle("Title"),
            content=content,
            occurred_at=_NOW,
        ),
        ADRSubmittedForReview(
            adr_id=adr_id,
            user_id=user_id,
            content=content,
            occurred_at=_LATER,
        ),
        AIReviewFailed(
            adr_id=adr_id,
            source_event_id=uuid4(),
            code="validation_failed",
            message="Invalid review output",
            occurred_at=_EVEN_LATER,
        ),
    ]

    adr = rehydrate_adr(events)

    assert adr is not None
    assert adr.status == AdrStatus.IN_REVIEW
    assert adr.review_error == ReviewError(
        code="validation_failed",
        message="Invalid review output",
    )
    assert adr.review_result is None


def test_rehydrate_adr_maps_soft_deleted() -> None:
    adr_id, user_id = _adr_ids()

    events = [
        ADRCreated(
            adr_id=adr_id,
            user_id=user_id,
            title=AdrTitle("Title"),
            content=AdrContent("## Context"),
            occurred_at=_NOW,
        ),
        ADRSoftDeleted(adr_id=adr_id, occurred_at=_LATER),
    ]

    adr = rehydrate_adr(events)

    assert adr is not None
    assert adr.is_deleted is True


class UnknownEvent(DomainEvent):
    pass


def test_rehydrate_adr_unknown_event_raises() -> None:
    adr_id, user_id = _adr_ids()

    events = [
        ADRCreated(
            adr_id=adr_id,
            user_id=user_id,
            title=AdrTitle("Title"),
            content=AdrContent("## Context"),
            occurred_at=_NOW,
        ),
        UnknownEvent(occurred_at=_LATER),
    ]

    with pytest.raises(ValueError, match="Unknown event type"):
        rehydrate_adr(events)
