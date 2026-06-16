"""Deterministic graders for ReviewResult quality evaluation."""

from domain.adr import SectionName
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)

from tests.review_quality.cases import ReviewQualityCase, ReviewQualityVerdict

_SECTION_NAMES: frozenset[str] = frozenset(section.value for section in SectionName)


def extract_flagged_sections(result: ReviewResult) -> frozenset[str]:
    """Return normalized section names flagged by missing_section annotations."""
    flagged: set[str] = set()
    for annotation in result.annotations:
        if annotation.kind != ReviewAnnotationKind.MISSING_SECTION:
            continue
        section = _section_from_annotation(annotation)
        if section is not None:
            flagged.add(section)
    return frozenset(flagged)


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
    failures: list[str] = []
    for index, annotation in enumerate(result.annotations):
        prefix = f"annotation {index} ({annotation.kind.value})"
        if annotation.kind == ReviewAnnotationKind.MISSING_SECTION:
            if not _is_non_empty(annotation.message):
                failures.append(f"{prefix}: non-empty message required")
            if not _is_non_empty(annotation.suggestion):
                failures.append(f"{prefix}: non-empty suggestion required")
        elif annotation.kind == ReviewAnnotationKind.CONCISENESS:
            if not _is_non_empty(annotation.message):
                failures.append(f"{prefix}: non-empty message required")
            if not _is_non_empty(annotation.suggestion):
                failures.append(f"{prefix}: non-empty suggestion required")
            if not _is_non_empty(annotation.location):
                failures.append(f"{prefix}: non-empty location required")
        elif annotation.kind == ReviewAnnotationKind.INCONSISTENCY:
            if not _is_non_empty(annotation.message):
                failures.append(f"{prefix}: non-empty message required")
            if not _is_non_empty(annotation.location):
                failures.append(f"{prefix}: non-empty location required")

    return not failures, tuple(failures)


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


def _section_from_annotation(annotation: ReviewAnnotation) -> str | None:
    if annotation.location is not None:
        section = _section_from_text(annotation.location)
        if section is not None:
            return section
    if annotation.message:
        return _section_from_text(annotation.message)
    return None


def _section_from_text(text: str) -> str | None:
    normalized = text.strip()
    if normalized.startswith("## "):
        normalized = normalized.removeprefix("## ").strip()
    if normalized in _SECTION_NAMES:
        return normalized
    for section_name in SectionName:
        if section_name.value in text:
            return section_name.value
    return None


def _is_non_empty(value: str | None) -> bool:
    return value is not None and bool(value.strip())
