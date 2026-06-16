"""Aggregate metrics reporting for the review quality harness.

The PRD ≥80% section-gap recall NFR applies to real LLM output validated in S-04,
not this deterministic golden fixture set where synthetic results are hand-crafted
to match expected gaps.
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
    precisions: list[float] = []
    recalls: list[float] = []

    for case in cases:
        verdict = grade_review_output(case, results[case.name])
        precisions.append(verdict.missing_section_precision)
        recalls.append(verdict.missing_section_recall)

    count = len(cases)
    return {
        "mean_precision": sum(precisions) / count,
        "mean_recall": sum(recalls) / count,
        "case_count": float(count),
    }


def test_golden_set_achieves_perfect_metrics(caplog: pytest.LogCaptureFixture) -> None:
    results = {case.name: build_synthetic_result(case) for case in ALL_CASES}
    metrics = compute_aggregate_metrics(ALL_CASES, results)

    assert metrics["mean_precision"] == 1.0
    assert metrics["mean_recall"] == 1.0
    assert metrics["case_count"] == float(len(ALL_CASES))

    summary = (
        f"review quality harness: {int(metrics['case_count'])} cases, "
        f"mean precision={metrics['mean_precision']:.2f}, "
        f"mean recall={metrics['mean_recall']:.2f}"
    )
    with caplog.at_level(logging.INFO):
        logger.info(summary)

    assert summary in caplog.text
