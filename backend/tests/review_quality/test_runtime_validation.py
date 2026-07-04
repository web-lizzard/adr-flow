"""Production runtime validation quality gate (F-01).

Proves the runtime validator enforces actionability and rating schema on
merged review output, and that the fake-LLM review pipeline produces valid
merged results with correct static gaps on all fixtures.
"""

import asyncio
from datetime import UTC, datetime

import pytest

from application.review_quality import validate_review_result
from application.services.adr_review_service import AdrReviewService
from domain.adr.required_sections import SectionName
from domain.adr.static_review import synthesize_static_review
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
    SectionRating,
)
from infrastructure.llm.fake_completion import FakeLlmCompletionPort
from tests.review_quality.cases import ALL_CASES, ReviewQualityCase
from tests.review_quality.grader import grade_review_output

_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _result(
    *annotations: ReviewAnnotation,
    section_ratings: tuple[SectionRating, ...] = (),
) -> ReviewResult:
    return ReviewResult(
        annotations=annotations,
        section_ratings=section_ratings,
        reviewed_at=_REVIEWED_AT,
    )


def _five_ratings(
    *, gap_sections: frozenset[str] = frozenset()
) -> tuple[SectionRating, ...]:
    return tuple(
        SectionRating(
            section=section,
            score=0 if section.value in gap_sections else 3,
            feedback="" if section.value in gap_sections else "Adequate.",
        )
        for section in SectionName
    )


def test_runtime_validator_accepts_valid_merged_result() -> None:
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
        section_ratings=_five_ratings(
            gap_sections=frozenset({"Decision", "Status", "Consequences"})
        ),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is True
    assert validation.failures == ()


def test_runtime_validator_rejects_incomplete_section_ratings() -> None:
    markdown = "## Context\n\nWe need a store.\n"
    result = _result(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message="Missing Options section",
            location="## Options",
            suggestion="List alternatives.",
        ),
        section_ratings=(
            SectionRating(section=SectionName.CONTEXT, score=3, feedback="Clear."),
        ),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is False
    assert any(
        "expected 5 section ratings" in failure for failure in validation.failures
    )


def test_runtime_validator_rejects_invalid_kind_specific_fields() -> None:
    markdown = "## Context\n\nDone\n"
    result = _result(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.CONCISENESS,
            message="Too verbose",
            location=None,
            suggestion="Shorten.",
        ),
        section_ratings=_five_ratings(),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is False
    assert any(
        "non-empty location required" in failure for failure in validation.failures
    )


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda case: case.name)
def test_static_synthesis_matches_fixture_expectations(case: ReviewQualityCase) -> None:
    annotations, ratings = synthesize_static_review(case.markdown)

    flagged = frozenset(
        annotation.location.removeprefix("## ").strip()
        for annotation in annotations
        if annotation.location is not None
    )
    assert flagged == case.expected_missing_sections

    rated_gap_sections = frozenset(
        rating.section.value for rating in ratings if rating.score == 0
    )
    assert rated_gap_sections == case.expected_missing_sections


async def _fake_review_all_fixtures() -> dict[str, ReviewResult]:
    service = AdrReviewService(FakeLlmCompletionPort())
    results: dict[str, ReviewResult] = {}
    for case in ALL_CASES:
        results[case.name] = await service.review_adr(case.markdown)
    return results


def test_fake_review_all_fixtures_pass_validation_and_harness() -> None:
    results = asyncio.run(_fake_review_all_fixtures())

    for case in ALL_CASES:
        result = results[case.name]
        validation = validate_review_result(case.markdown, result)
        assert validation.passed is True, f"{case.name}: {validation.failures}"
        verdict = grade_review_output(case, result)
        assert verdict.passed is True, f"{case.name}: {verdict.failures}"
