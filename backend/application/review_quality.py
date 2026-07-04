"""Runtime-safe review output validation for AI review workers."""

from dataclasses import dataclass

from domain.adr.required_sections import SectionName
from domain.adr.review_actionability import required_fields_for_kind
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
    SectionRating,
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
    """Validate actionability and section rating schema for review output."""
    del markdown
    rating_failures = _section_rating_failures(result.section_ratings)
    actionability_failures = _actionability_failures(result)
    failures = rating_failures + actionability_failures
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


def _section_rating_failures(
    section_ratings: tuple[SectionRating, ...],
) -> tuple[str, ...]:
    failures: list[str] = []
    expected_count = len(SectionName)

    if len(section_ratings) != expected_count:
        failures.append(
            f"expected {expected_count} section ratings, got {len(section_ratings)}"
        )

    rated_sections = [rating.section for rating in section_ratings]
    if len(rated_sections) != len(set(rated_sections)):
        failures.append("duplicate section ratings")

    missing_sections = set(SectionName) - set(rated_sections)
    if missing_sections:
        missing = ", ".join(section.value for section in missing_sections)
        failures.append(f"missing section ratings: {missing}")

    for index, rating in enumerate(section_ratings):
        prefix = f"section rating {index} ({rating.section.value})"
        if rating.score < 0 or rating.score > 5:
            failures.append(f"{prefix}: score must be between 0 and 5")
        if rating.score >= 1 and not rating.feedback.strip():
            failures.append(f"{prefix}: non-empty feedback required")

    return tuple(failures)


def _actionability_failures(result: ReviewResult) -> tuple[str, ...]:
    failures: list[str] = []
    for index, annotation in enumerate(result.annotations):
        prefix = f"annotation {index} ({annotation.kind.value})"
        for field_name in required_fields_for_kind(annotation.kind):
            if not _is_non_empty(getattr(annotation, field_name)):
                failures.append(f"{prefix}: non-empty {field_name} required")
    return tuple(failures)
