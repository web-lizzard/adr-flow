"""Deterministic graders for ReviewResult quality evaluation."""

from application.review_quality import check_actionability, extract_flagged_sections
from domain.adr.value_objects import ReviewResult

from tests.review_quality.cases import ReviewQualityCase, ReviewQualityVerdict


def grade_missing_section_annotations(
    case: ReviewQualityCase,
    result: ReviewResult,
) -> tuple[float, float, tuple[str, ...]]:
    """Compute precision/recall for missing-section coverage."""
    expected = case.expected_missing_sections
    flagged = extract_flagged_sections(result)

    true_positives = expected & flagged
    false_positives = flagged - expected
    false_negatives = expected - flagged

    precision = 1.0 if not flagged else len(true_positives) / len(flagged)
    recall = 1.0 if not expected else len(true_positives) / len(expected)

    failures: list[str] = []
    for section in sorted(false_positives):
        failures.append(
            f"false positive: unexpected missing_section annotation for {section}"
        )
    for section in sorted(false_negatives):
        failures.append(f"false negative: missing annotation for {section}")

    return precision, recall, tuple(failures)


def grade_actionability(result: ReviewResult) -> tuple[bool, tuple[str, ...]]:
    """Enforce kind-specific actionability rules on all annotations."""
    return check_actionability(result)


def grade_review_output(
    case: ReviewQualityCase,
    result: ReviewResult,
) -> ReviewQualityVerdict:
    """Combine missing-section and actionability grades into a verdict."""
    precision, recall, missing_failures = grade_missing_section_annotations(
        case, result
    )
    actionability_passed, actionability_failures = grade_actionability(result)
    failures = missing_failures + actionability_failures
    passed = precision == 1.0 and recall == 1.0 and actionability_passed
    return ReviewQualityVerdict(
        passed=passed,
        missing_section_precision=precision,
        missing_section_recall=recall,
        failures=failures,
    )
