"""End-to-end harness tests for required-section detection and grading."""

from datetime import UTC, datetime

import pytest

from domain.adr import find_missing_or_empty_sections
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from tests.review_quality.cases import (
    ALL_CASES,
    ReviewQualityCase,
    build_synthetic_result,
)
from tests.review_quality.grader import grade_review_output

_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _sections_from_markdown(markdown: str) -> frozenset[str]:
    return frozenset(
        section.value for section in find_missing_or_empty_sections(markdown)
    )


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda case: case.name)
def test_parser_ground_truth_matches_fixture_expectations(
    case: ReviewQualityCase,
) -> None:
    assert _sections_from_markdown(case.markdown) == case.expected_missing_sections


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda case: case.name)
def test_synthetic_result_passes_grader(case: ReviewQualityCase) -> None:
    result = build_synthetic_result(case)
    verdict = grade_review_output(case, result)
    assert verdict.passed is True


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda case: case.name)
def test_incomplete_result_fails_grader(case: ReviewQualityCase) -> None:
    if not case.expected_missing_sections:
        pytest.skip("no expected gaps to omit")

    sections = sorted(case.expected_missing_sections)
    omitted = sections[0]
    remaining = sections[1:]

    annotations = tuple(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message=f"Missing {section} section",
            location=f"## {section}",
            suggestion=f"Add content for {section}.",
        )
        for section in remaining
    )
    result = ReviewResult(annotations=annotations, reviewed_at=_REVIEWED_AT)
    verdict = grade_review_output(case, result)

    assert verdict.passed is False
    assert f"false negative: missing annotation for {omitted}" in verdict.failures
