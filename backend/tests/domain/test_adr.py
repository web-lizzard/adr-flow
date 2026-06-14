"""ADR domain vocabulary construction tests."""

from datetime import UTC, datetime
from uuid import uuid4

from domain.adr import (
    ADR,
    ADRContentUpdated,
    ADRCreated,
    ADRPublished,
    ADRSoftDeleted,
    ADRSubmittedForReview,
    AIReviewCompleted,
    AdrContent,
    AdrId,
    AdrStatus,
    AdrTitle,
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from domain.user import UserId

ADR_EVENT_NAMES = frozenset(
    {
        "ADRCreated",
        "ADRContentUpdated",
        "ADRSubmittedForReview",
        "AIReviewCompleted",
        "ADRPublished",
        "ADRSoftDeleted",
    }
)


def test_adr_status_values_match_mvp_contract() -> None:
    assert {status.value for status in AdrStatus} == {
        "draft",
        "in_review",
        "after_review",
        "proposed",
    }


def test_adr_event_vocabulary_includes_content_updated() -> None:
    assert "ADRContentUpdated" in ADR_EVENT_NAMES
    assert ADRContentUpdated.__name__ == "ADRContentUpdated"


def test_adr_aggregate_and_events_construct() -> None:
    adr_id = AdrId(uuid4())
    user_id = UserId(uuid4())
    title = AdrTitle("Choose event store")
    content = AdrContent("## Context\n\nTBD")
    now = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)

    adr = ADR(
        adr_id=adr_id,
        user_id=user_id,
        title=title,
        content=content,
        status=AdrStatus.DRAFT,
        review_result=None,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )

    assert adr.status == AdrStatus.DRAFT
    assert adr.review_result is None
    assert adr.is_deleted is False

    created = ADRCreated(
        adr_id=adr_id,
        user_id=user_id,
        title=title,
        content=content,
        occurred_at=now,
    )
    content_updated = ADRContentUpdated(
        adr_id=adr_id,
        content=AdrContent("## Context\n\nUpdated"),
        occurred_at=now,
    )
    submitted = ADRSubmittedForReview(adr_id=adr_id, occurred_at=now)
    annotation = ReviewAnnotation(
        kind=ReviewAnnotationKind.MISSING_SECTION,
        message="Missing Consequences section",
        location="## Consequences",
    )
    review_result = ReviewResult(
        annotations=(annotation,),
        reviewed_at=now,
        reviewed_content=content.value,
    )
    reviewed = AIReviewCompleted(
        adr_id=adr_id,
        review_result=review_result,
        occurred_at=now,
    )
    published = ADRPublished(adr_id=adr_id, occurred_at=now)
    deleted = ADRSoftDeleted(adr_id=adr_id, occurred_at=now)

    event_names = {
        created.__class__.__name__,
        content_updated.__class__.__name__,
        submitted.__class__.__name__,
        reviewed.__class__.__name__,
        published.__class__.__name__,
        deleted.__class__.__name__,
    }
    assert event_names == ADR_EVENT_NAMES
