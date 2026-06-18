"""Production runtime validation quality gate (F-01).

Proves the runtime validator enforces the same actionability and
missing-section constraints as the harness, and that deterministic fake
completion output meets the PRD section-gap recall threshold on fixtures.
"""

import asyncio
from datetime import UTC, datetime

from application.review_quality import validate_review_result
from application.services.adr_review_service import AdrReviewService
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from infrastructure.llm.fake_completion import FakeLlmCompletionPort
from tests.review_quality.cases import ALL_CASES
from tests.review_quality.grader import grade_review_output

PRD_RECALL_THRESHOLD = 0.80
_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _result(*annotations: ReviewAnnotation) -> ReviewResult:
    return ReviewResult(annotations=annotations, reviewed_at=_REVIEWED_AT)


def test_runtime_validator_accepts_valid_missing_section_coverage() -> None:
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


def test_runtime_validator_rejects_missing_required_section_annotation() -> None:
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


def test_runtime_validator_rejects_invalid_kind_specific_fields() -> None:
    markdown = "## Context\n\nDone\n"
    result = _result(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.CONCISENESS,
            message="Too verbose",
            location=None,
            suggestion="Shorten.",
        ),
    )

    validation = validate_review_result(markdown, result)

    assert validation.passed is False
    assert any(
        "non-empty location required" in failure for failure in validation.failures
    )


async def _fake_review_all_fixtures() -> dict[str, ReviewResult]:
    service = AdrReviewService(FakeLlmCompletionPort())
    results: dict[str, ReviewResult] = {}
    for case in ALL_CASES:
        results[case.name] = await service.review_adr(case.markdown)
    return results


def test_fake_completion_fixture_recall_meets_prd_threshold() -> None:
    results = asyncio.run(_fake_review_all_fixtures())
    recalls: list[float] = []

    for case in ALL_CASES:
        result = results[case.name]
        validation = validate_review_result(case.markdown, result)
        assert validation.passed is True, f"{case.name}: {validation.failures}"
        verdict = grade_review_output(case, result)
        recalls.append(verdict.missing_section_recall)

    mean_recall = sum(recalls) / len(recalls)
    assert mean_recall >= PRD_RECALL_THRESHOLD
