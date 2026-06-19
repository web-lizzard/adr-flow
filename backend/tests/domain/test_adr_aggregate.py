"""ADR aggregate command methods and transition helpers."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.adr.aggregate import ADR
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
from domain.errors import (
    AdrEditWhileInReview,
    AdrInvalidPublishStatus,
    AdrInvalidReviewStatus,
    AdrInvalidSubmitStatus,
)
from domain.user.value_objects import UserId

_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
_LATER = datetime(2026, 6, 18, 13, 0, tzinfo=UTC)


def _draft_adr() -> ADR:
    return ADR.create(
        adr_id=AdrId(uuid4()),
        user_id=UserId(uuid4()),
        title=AdrTitle("Choose event store"),
        content=AdrContent("## Context\n\nTBD"),
        created_at=_NOW,
    )


def test_create_initializes_draft_with_cleared_review_fields() -> None:
    adr = _draft_adr()

    assert adr.status == AdrStatus.DRAFT
    assert adr.review_result is None
    assert adr.review_error is None
    assert adr.reviewed_at is None
    assert adr.is_deleted is False


def test_submit_for_review_transitions_draft_to_in_review() -> None:
    adr = _draft_adr()

    submitted = adr.submit_for_review(updated_at=_LATER)

    assert submitted.status == AdrStatus.IN_REVIEW
    assert submitted.updated_at == _LATER


def test_with_submitted_for_review_clears_review_fields() -> None:
    adr = replace(
        _draft_adr(),
        review_result=ReviewResult(
            annotations=(
                ReviewAnnotation(
                    kind=ReviewAnnotationKind.MISSING_SECTION,
                    message="Missing section",
                ),
            ),
            reviewed_at=_NOW,
        ),
        review_error=ReviewError(code="validation_failed", message="bad output"),
        reviewed_at=_NOW,
    )

    submitted = adr.with_submitted_for_review(updated_at=_LATER)

    assert submitted.review_result is None
    assert submitted.review_error is None
    assert submitted.reviewed_at is None
    assert submitted.status == AdrStatus.IN_REVIEW


def test_submit_for_review_rejects_non_draft() -> None:
    adr = _draft_adr().with_submitted_for_review(updated_at=_LATER)

    with pytest.raises(AdrInvalidSubmitStatus):
        adr.submit_for_review(updated_at=_LATER)


def test_update_content_rejects_in_review() -> None:
    adr = _draft_adr().with_submitted_for_review(updated_at=_LATER)

    with pytest.raises(AdrEditWhileInReview):
        adr.update_content(
            content=AdrContent("## Context\n\nUpdated"),
            updated_at=_LATER,
        )


def test_update_title_rejects_in_review() -> None:
    adr = _draft_adr().with_submitted_for_review(updated_at=_LATER)

    with pytest.raises(AdrEditWhileInReview):
        adr.update_title(title=AdrTitle("New title"), updated_at=_LATER)


def test_update_content_during_after_review_preserves_review_annotations() -> None:
    review_result = ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing section",
            ),
        ),
        reviewed_at=_NOW,
    )
    adr = (
        _draft_adr()
        .with_submitted_for_review(updated_at=_NOW)
        .with_review_completed(result=review_result, reviewed_at=_NOW)
    )

    updated = adr.update_content(
        content=AdrContent("## Context\n\nEdited after review"),
        updated_at=_LATER,
    )

    assert updated.status == AdrStatus.AFTER_REVIEW
    assert updated.review_result == review_result
    assert updated.reviewed_at == _NOW
    assert updated.title == adr.title


def test_update_title_during_after_review_preserves_review_annotations() -> None:
    review_result = ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing section",
            ),
        ),
        reviewed_at=_NOW,
    )
    adr = (
        _draft_adr()
        .with_submitted_for_review(updated_at=_NOW)
        .with_review_completed(result=review_result, reviewed_at=_NOW)
    )

    updated = adr.update_title(title=AdrTitle("Updated title"), updated_at=_LATER)

    assert updated.status == AdrStatus.AFTER_REVIEW
    assert updated.review_result == review_result
    assert updated.reviewed_at == _NOW
    assert updated.title == AdrTitle("Updated title")
    assert updated.content == adr.content


def test_publish_preserves_review_fields_after_review_completed() -> None:
    review_result = ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing section",
            ),
        ),
        reviewed_at=_NOW,
    )
    adr = (
        _draft_adr()
        .with_submitted_for_review(updated_at=_NOW)
        .with_review_completed(result=review_result, reviewed_at=_NOW)
    )

    published = adr.publish(updated_at=_LATER)

    assert published.status == AdrStatus.PROPOSED
    assert published.review_result == review_result
    assert published.reviewed_at == _NOW


def test_publish_rejects_draft() -> None:
    adr = _draft_adr()

    with pytest.raises(AdrInvalidPublishStatus):
        adr.publish(updated_at=_LATER)


def test_with_review_failed_sets_error_and_clears_review_result() -> None:
    adr = _draft_adr().with_submitted_for_review(updated_at=_NOW)

    failed = adr.with_review_failed(
        code="validation_failed",
        message="Invalid review output",
    )

    assert failed.review_error == ReviewError(
        code="validation_failed",
        message="Invalid review output",
    )
    assert failed.review_result is None
    assert failed.status == AdrStatus.IN_REVIEW


def test_with_soft_deleted_sets_is_deleted() -> None:
    adr = _draft_adr()

    deleted = adr.with_soft_deleted()

    assert deleted.is_deleted is True
    assert deleted.status == AdrStatus.DRAFT


def _in_review_adr() -> ADR:
    return _draft_adr().with_submitted_for_review(updated_at=_NOW)


def test_complete_review_transitions_in_review_to_after_review() -> None:
    adr = _in_review_adr()
    review_result = ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing section",
            ),
        ),
        reviewed_at=_LATER,
    )

    completed = adr.complete_review(result=review_result, reviewed_at=_LATER)

    assert completed.status == AdrStatus.AFTER_REVIEW
    assert completed.review_result == review_result
    assert completed.reviewed_at == _LATER
    assert completed.review_error is None


def test_complete_review_rejects_draft() -> None:
    adr = _draft_adr()
    review_result = ReviewResult(annotations=(), reviewed_at=_LATER)

    with pytest.raises(AdrInvalidReviewStatus):
        adr.complete_review(result=review_result, reviewed_at=_LATER)


def test_complete_review_rejects_after_review() -> None:
    adr = _in_review_adr().with_review_completed(
        result=ReviewResult(annotations=(), reviewed_at=_NOW),
        reviewed_at=_NOW,
    )

    with pytest.raises(AdrInvalidReviewStatus):
        adr.complete_review(
            result=ReviewResult(annotations=(), reviewed_at=_LATER),
            reviewed_at=_LATER,
        )


def test_fail_review_records_error_while_in_review() -> None:
    adr = _in_review_adr()

    failed = adr.fail_review(code="validation_failed", message="bad output")

    assert failed.status == AdrStatus.IN_REVIEW
    assert failed.review_error == ReviewError(
        code="validation_failed",
        message="bad output",
    )
    assert failed.review_result is None


def test_fail_review_rejects_draft() -> None:
    adr = _draft_adr()

    with pytest.raises(AdrInvalidReviewStatus):
        adr.fail_review(code="validation_failed", message="bad output")


def test_fail_review_rejects_after_review() -> None:
    adr = _in_review_adr().with_review_completed(
        result=ReviewResult(annotations=(), reviewed_at=_NOW),
        reviewed_at=_NOW,
    )

    with pytest.raises(AdrInvalidReviewStatus):
        adr.fail_review(code="validation_failed", message="bad output")
