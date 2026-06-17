"""ADR API schema contract tests."""

from datetime import UTC, datetime
from uuid import uuid4

from application.review_metadata import ReviewErrorMetadata
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from infrastructure.api.schemas.adr import (
    AdrResponse,
    ReviewAnnotationResponse,
    ReviewErrorResponse,
    ReviewStatusResponse,
    annotation_counts_from_result,
)


def test_adr_response_includes_review_fields() -> None:
    reviewed_at = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    failed_at = datetime(2026, 6, 17, 13, 0, tzinfo=UTC)
    source_event_id = uuid4()

    response = AdrResponse(
        id=uuid4(),
        title="ADR title",
        content="## Context",
        status="after_review",
        created_at=reviewed_at,
        updated_at=reviewed_at,
        review_annotations=[
            ReviewAnnotationResponse(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Consequences section",
                location="## Consequences",
                suggestion="Describe trade-offs.",
            )
        ],
        reviewed_at=reviewed_at,
        review_error=ReviewErrorResponse.from_metadata(
            ReviewErrorMetadata(
                source_event_id=source_event_id,
                code="validation_failed",
                message="Invalid review output",
                failed_at=failed_at,
            )
        ),
    )

    assert response.review_annotations is not None
    assert response.reviewed_at == reviewed_at
    assert response.review_error is not None
    assert response.review_error.code == "validation_failed"


def test_review_status_response_exposes_counts() -> None:
    reviewed_at = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    result = ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Consequences section",
                location="## Consequences",
                suggestion="Describe trade-offs.",
            ),
            ReviewAnnotation(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="Status conflicts with Decision",
                location="## Status",
            ),
        ),
        reviewed_at=reviewed_at,
    )

    response = ReviewStatusResponse(
        status="after_review",
        reviewed_at=reviewed_at,
        annotation_counts=annotation_counts_from_result(result),
    )

    assert response.annotation_counts == {
        "missing_section": 1,
        "inconsistency": 1,
    }
