"""Unit tests for review quality grader logic."""

from datetime import UTC, datetime

import pytest

from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from tests.review_quality.cases import ReviewQualityCase
from tests.review_quality.grader import (
    extract_flagged_sections,
    grade_actionability,
    grade_missing_section_annotations,
    grade_review_output,
)

_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)

_COMPLETE_ADR = """\
## Context

We need to choose a database for the project.

## Options

1. PostgreSQL
2. MongoDB

## Decision

We will use PostgreSQL.

## Status

Accepted

## Consequences

Positive: ACID compliance. Negative: operational overhead.
"""


def _missing_section_annotation(
    section: str,
    *,
    message: str | None = None,
    location: str | None = None,
    suggestion: str | None = "Add content for this section.",
) -> ReviewAnnotation:
    return ReviewAnnotation(
        kind=ReviewAnnotationKind.MISSING_SECTION,
        message=message or f"Missing {section} section",
        location=location or f"## {section}",
        suggestion=suggestion,
    )


def _result(*annotations: ReviewAnnotation) -> ReviewResult:
    return ReviewResult(annotations=annotations, reviewed_at=_NOW)


def _case(
    *,
    name: str = "test-case",
    markdown: str = _COMPLETE_ADR,
    expected_missing_sections: frozenset[str] = frozenset(),
) -> ReviewQualityCase:
    return ReviewQualityCase(
        name=name,
        markdown=markdown,
        expected_missing_sections=expected_missing_sections,
    )


def test_perfect_match_passes() -> None:
    case = _case(expected_missing_sections=frozenset({"Context", "Decision"}))
    result = _result(
        _missing_section_annotation("Context"),
        _missing_section_annotation("Decision"),
    )

    verdict = grade_review_output(case, result)

    assert verdict.passed is True
    assert verdict.missing_section_precision == 1.0
    assert verdict.missing_section_recall == 1.0
    assert verdict.failures == ()


def test_false_positive_fails_precision() -> None:
    case = _case(expected_missing_sections=frozenset({"Context"}))
    result = _result(
        _missing_section_annotation("Context"),
        _missing_section_annotation("Options"),
    )

    precision, recall, failures = grade_missing_section_annotations(case, result)

    assert precision == 0.5
    assert recall == 1.0
    assert (
        "false positive: unexpected missing_section annotation for Options" in failures
    )


def test_false_negative_fails_recall() -> None:
    case = _case(expected_missing_sections=frozenset({"Context", "Decision"}))
    result = _result(_missing_section_annotation("Context"))

    precision, recall, failures = grade_missing_section_annotations(case, result)

    assert precision == 1.0
    assert recall == 0.5
    assert "false negative: missing annotation for Decision" in failures


def test_empty_annotations_with_expected_gaps_fails_recall() -> None:
    case = _case(expected_missing_sections=frozenset({"Status"}))
    result = _result()

    verdict = grade_review_output(case, result)

    assert verdict.passed is False
    assert verdict.missing_section_recall == 0.0
    assert "false negative: missing annotation for Status" in verdict.failures


def test_complete_adr_with_empty_annotations_passes() -> None:
    case = _case()
    result = _result()

    verdict = grade_review_output(case, result)

    assert verdict.passed is True
    assert verdict.missing_section_precision == 1.0
    assert verdict.missing_section_recall == 1.0


def test_extract_flagged_sections_from_location_and_message() -> None:
    result = _result(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="The Consequences section is absent",
            location="## Consequences",
        ),
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="Missing Options section",
            location=None,
        ),
    )

    assert extract_flagged_sections(result) == frozenset({"Consequences", "Options"})


@pytest.mark.parametrize(
    ("annotation", "expected_failure"),
    [
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="",
                suggestion="Add content",
                location="## Context",
            ),
            "non-empty message required",
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Context",
                suggestion="   ",
                location="## Context",
            ),
            "non-empty suggestion required",
        ),
        (
            ReviewAnnotation(
                kind=ReviewAnnotationKind.CONCISENESS,
                message="Too verbose",
                suggestion="Shorten this",
                location=None,
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
                message="",
                location="## Status",
            ),
            "non-empty message required",
        ),
    ],
)
def test_actionability_failures_per_kind(
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


def test_grade_review_output_fails_when_actionability_fails() -> None:
    case = _case(expected_missing_sections=frozenset({"Context"}))
    result = _result(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="Missing Context section",
            location="## Context",
            suggestion=None,
        )
    )

    verdict = grade_review_output(case, result)

    assert verdict.passed is False
    assert verdict.missing_section_precision == 1.0
    assert verdict.missing_section_recall == 1.0
    assert any(
        "non-empty suggestion required" in failure for failure in verdict.failures
    )
