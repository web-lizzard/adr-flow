"""Aggregate metrics reporting for the review quality harness.

The harness grades static gap presence and annotation actionability on
fixture-driven synthetic or merged review results — not LLM recall against
a precision/recall threshold.
"""

import logging

import pytest

from domain.adr.value_objects import ReviewResult
from tests.review_quality.cases import (
    ALL_CASES,
    ReviewQualityCase,
    build_synthetic_result,
)
from tests.review_quality.grader import grade_review_output

logger = logging.getLogger(__name__)


def compute_aggregate_metrics(
    cases: tuple[ReviewQualityCase, ...],
    results: dict[str, ReviewResult],
) -> dict[str, float]:
    passed_count = sum(
        1 for case in cases if grade_review_output(case, results[case.name]).passed
    )
    count = len(cases)
    return {
        "pass_rate": passed_count / count,
        "case_count": float(count),
    }


def test_golden_set_achieves_perfect_pass_rate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    results = {case.name: build_synthetic_result(case) for case in ALL_CASES}
    metrics = compute_aggregate_metrics(ALL_CASES, results)

    assert metrics["pass_rate"] == 1.0
    assert metrics["case_count"] == float(len(ALL_CASES))

    summary = (
        f"review quality harness: {int(metrics['case_count'])} cases, "
        f"pass rate={metrics['pass_rate']:.2f}"
    )
    with caplog.at_level(logging.INFO):
        logger.info(summary)

    assert summary in caplog.text
