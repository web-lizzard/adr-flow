"""Production review validation tests."""

from datetime import UTC, datetime

import pytest

from application.review_quality import validate_review_result
from domain.adr.required_sections import SectionName
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
    SectionRating,
)

_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _all_section_ratings(
    *,
    gap_sections: frozenset[SectionName] = frozenset(),
) -> tuple[SectionRating, ...]:
    return tuple(
        SectionRating(
            section=section,
            score=0 if section in gap_sections else 3,
            feedback="" if section in gap_sections else "Adequate content.",
        )
        for section in SectionName
    )


def _result(
    *annotations: ReviewAnnotation,
    section_ratings: tuple[SectionRating, ...] | None = None,
) -> ReviewResult:
    return ReviewResult(
        annotations=annotations,
        reviewed_at=_REVIEWED_AT,
        section_ratings=section_ratings or _all_section_ratings(),
    )


def test_validate_review_result_accepts_complete_section_ratings() -> None:
    markdown = "## Context\n\nWe need a store.\n\n## Options\n\nA or B.\n"
    gap_sections = frozenset(
        {SectionName.DECISION, SectionName.STATUS, SectionName.CONSEQUENCES}
    )
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
        section_ratings=_all_section_ratings(gap_sections=gap_sections),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is True
    assert validation.failures == ()


def test_validate_review_result_rejects_missing_section_ratings() -> None:
    markdown = "## Context\n\nDone\n"
    result = ReviewResult(
        annotations=(),
        reviewed_at=_REVIEWED_AT,
        section_ratings=(
            SectionRating(section=SectionName.CONTEXT, score=3, feedback="Clear."),
            SectionRating(section=SectionName.OPTIONS, score=2, feedback="Thin."),
        ),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is False
    assert any(
        "expected 5 section ratings" in failure for failure in validation.failures
    )


def test_validate_review_result_rejects_duplicate_section_ratings() -> None:
    markdown = "## Context\n\nDone\n"
    ratings = _all_section_ratings()
    duplicate_ratings = ratings + (
        SectionRating(section=SectionName.CONTEXT, score=4, feedback="Again."),
    )
    result = ReviewResult(
        annotations=(),
        reviewed_at=_REVIEWED_AT,
        section_ratings=duplicate_ratings,
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is False
    assert any("duplicate section" in failure for failure in validation.failures)


def test_validate_review_result_rejects_empty_feedback_for_scored_sections() -> None:
    markdown = "## Context\n\nDone\n"
    ratings = list(_all_section_ratings())
    ratings[0] = SectionRating.model_construct(
        section=SectionName.CONTEXT,
        score=2,
        feedback="",
    )
    result = ReviewResult(
        annotations=(),
        reviewed_at=_REVIEWED_AT,
        section_ratings=tuple(ratings),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is False
    assert any(
        "non-empty feedback required" in failure for failure in validation.failures
    )


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
