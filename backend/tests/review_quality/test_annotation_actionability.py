"""Harness tests for annotation actionability rules across kinds."""

from datetime import UTC, datetime

import pytest

from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from tests.review_quality.grader import grade_actionability

_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _result(*annotations: ReviewAnnotation) -> ReviewResult:
    return ReviewResult(annotations=annotations, reviewed_at=_REVIEWED_AT)


@pytest.mark.parametrize(
    ("annotation", "expected_failure"),
    [
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Context section",
                location="## Context",
                suggestion="Add context describing the problem.",
            ),
            None,
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="",
                location="## Context",
                suggestion="Add context.",
            ),
            "non-empty message required",
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Context section",
                location="## Context",
                suggestion="  ",
            ),
            "non-empty suggestion required",
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.CONCISENESS,
                message="Section is too verbose",
                location="## Context",
                suggestion="Shorten to key points.",
            ),
            None,
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.CONCISENESS,
                message="Section is too verbose",
                location=None,
                suggestion="Shorten to key points.",
            ),
            "non-empty location required",
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="Status conflicts with Decision",
                location="## Status",
            ),
            None,
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="Status conflicts with Decision",
                location="## Status",
                suggestion=None,
            ),
            None,
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="",
                location="## Status",
            ),
            "non-empty message required",
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="Status conflicts with Decision",
                location=None,
            ),
            "non-empty location required",
        ),
    ],
)
def test_actionability_rules(
    annotation: ReviewAnnotation,
    expected_failure: str | None,
) -> None:
    passed, failures = grade_actionability(_result(annotation))

    if expected_failure is None:
        assert passed is True
        assert failures == ()
    else:
        assert passed is False
        assert any(expected_failure in failure for failure in failures)
