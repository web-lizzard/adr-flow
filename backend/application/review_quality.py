"""Runtime-safe review output validation for AI review workers."""

from dataclasses import dataclass

from domain.adr import SectionName, find_missing_or_empty_sections
from domain.adr.review_actionability import required_fields_for_kind
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)

_SECTION_NAMES_BY_CASEFOLD: dict[str, str] = {
    section.value.casefold(): section.value for section in SectionName
}


@dataclass(frozen=True, slots=True)
class ReviewValidationResult:
    passed: bool
    failures: tuple[str, ...]


def validate_review_result(
    markdown: str,
    result: ReviewResult,
) -> ReviewValidationResult:
    """Validate actionability and missing-section coverage for review output."""
    missing_failures = _missing_section_failures(markdown, result)
    actionability_failures = _actionability_failures(result)
    failures = missing_failures + actionability_failures
    return ReviewValidationResult(passed=not failures, failures=failures)


def extract_flagged_sections(result: ReviewResult) -> frozenset[str]:
    """Return normalized section names flagged by missing_section annotations."""
    return _flagged_missing_sections(result)


def check_actionability(result: ReviewResult) -> tuple[bool, tuple[str, ...]]:
    """Enforce kind-specific actionability rules on all annotations."""
    failures = _actionability_failures(result)
    return not failures, failures


def _flagged_missing_sections(result: ReviewResult) -> frozenset[str]:
    flagged: set[str] = set()
    for annotation in result.annotations:
        if annotation.kind != ReviewAnnotationKind.MISSING_SECTION:
            continue
        section = _section_from_annotation(annotation)
        if section is not None:
            flagged.add(section)
    return frozenset(flagged)


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
    section = _SECTION_NAMES_BY_CASEFOLD.get(normalized.casefold())
    if section is not None:
        return section
    casefolded_text = text.casefold()
    for section_name in SectionName:
        if section_name.value.casefold() in casefolded_text:
            return section_name.value
    return None


def _is_non_empty(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _missing_section_failures(
    markdown: str,
    result: ReviewResult,
) -> tuple[str, ...]:
    expected = frozenset(
        section.value for section in find_missing_or_empty_sections(markdown)
    )
    flagged = _flagged_missing_sections(result)

    failures: list[str] = []
    for section in sorted(flagged - expected):
        failures.append(
            f"false positive: unexpected missing_section annotation for {section}"
        )
    for section in sorted(expected - flagged):
        failures.append(f"false negative: missing annotation for {section}")
    return tuple(failures)


def _actionability_failures(result: ReviewResult) -> tuple[str, ...]:
    failures: list[str] = []
    for index, annotation in enumerate(result.annotations):
        prefix = f"annotation {index} ({annotation.kind.value})"
        for field_name in required_fields_for_kind(annotation.kind):
            if not _is_non_empty(getattr(annotation, field_name)):
                failures.append(f"{prefix}: non-empty {field_name} required")
    return tuple(failures)
