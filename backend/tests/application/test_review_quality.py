"""Production review validation tests."""

from datetime import UTC, datetime

import pytest

from application.review_quality import validate_review_result
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)

_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _result(*annotations: ReviewAnnotation) -> ReviewResult:
    return ReviewResult(annotations=annotations, reviewed_at=_REVIEWED_AT)


def test_validate_review_result_accepts_actionable_missing_section_coverage() -> None:
    markdown = "## Context\n\nWe need a store.\n\n## Options\n\nA or B.\n"
    result = _result(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="Missing Decision section",
            location="## Decision",
            suggestion="Document the chosen option.",
        ),
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="Missing Status section",
            location="## Status",
            suggestion="Record the current status.",
        ),
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="Missing Consequences section",
            location="## Consequences",
            suggestion="Describe trade-offs.",
        ),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is True
    assert validation.failures == ()


def test_validate_review_result_accepts_case_insensitive_section_text() -> None:
    markdown = (
        "## Context\n\nWe need a store.\n\n"
        "## Options\n\nA or B.\n\n"
        "## Status\n\nDraft.\n\n"
        "## Consequences\n\nTrade-offs."
    )
    result = _result(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="missing decision section",
            suggestion="Document the chosen option.",
        )
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is True
    assert validation.failures == ()


def test_validate_review_result_rejects_missing_section_gaps() -> None:
    markdown = "## Context\n\nWe need a store.\n"
    result = _result(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="Missing Options section",
            location="## Options",
            suggestion="List alternatives.",
        ),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is False
    assert any("Decision" in failure for failure in validation.failures)


@pytest.mark.parametrize(
    ("annotation", "expected_failure"),
    [
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
                kind=ReviewAnnotationKind.CONCISENESS,
                message="Too verbose",
                location=None,
                suggestion="Shorten.",
            ),
            "non-empty location required",
        ),
    ],
)
def test_validate_review_result_rejects_non_actionable_annotations(
    annotation: ReviewAnnotation,
    expected_failure: str,
) -> None:
    markdown = "## Context\n\nDone\n"
    validation = validate_review_result(markdown, _result(annotation))

    assert validation.passed is False
    assert any(expected_failure in failure for failure in validation.failures)
