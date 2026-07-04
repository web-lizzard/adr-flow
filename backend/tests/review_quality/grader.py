"""Deterministic graders for ReviewResult quality evaluation."""

from application.review_quality import check_actionability, extract_flagged_sections
from domain.adr.value_objects import ReviewResult

from tests.review_quality.cases import ReviewQualityCase, ReviewQualityVerdict


def grade_static_gap_presence(
    case: ReviewQualityCase,
    result: ReviewResult,
) -> tuple[bool, tuple[str, ...]]:
    """Check missing_section annotations match expected static gaps."""
    expected = case.expected_missing_sections
    flagged = extract_flagged_sections(result)

    if flagged == expected:
        return True, ()

    failures: list[str] = []
    for section in sorted(flagged - expected):
        failures.append(f"unexpected missing_section annotation for {section}")
    for section in sorted(expected - flagged):
        failures.append(f"missing static gap annotation for {section}")
    return False, tuple(failures)


def grade_actionability(result: ReviewResult) -> tuple[bool, tuple[str, ...]]:
    """Enforce kind-specific actionability rules on all annotations."""
    return check_actionability(result)


def grade_review_output(
    case: ReviewQualityCase,
    result: ReviewResult,
) -> ReviewQualityVerdict:
    """Combine static gap presence and actionability into a verdict."""
    static_gaps_passed, static_failures = grade_static_gap_presence(case, result)
    actionability_passed, actionability_failures = grade_actionability(result)
    failures = static_failures + actionability_failures
    passed = static_gaps_passed and actionability_passed
    return ReviewQualityVerdict(passed=passed, failures=failures)
