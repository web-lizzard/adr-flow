"""Shared actionability rules for review annotations."""

from domain.adr.value_objects import ReviewAnnotationKind

_REQUIRED_FIELDS: dict[ReviewAnnotationKind, tuple[str, ...]] = {
    ReviewAnnotationKind.MISSING_SECTION: ("message", "suggestion"),
    ReviewAnnotationKind.INCONSISTENCY: ("message", "location"),
    ReviewAnnotationKind.CONCISENESS: ("message", "suggestion", "location"),
}


def required_fields_for_kind(kind: ReviewAnnotationKind) -> tuple[str, ...]:
    """Return required non-empty field names for a review annotation kind."""
    return _REQUIRED_FIELDS[kind]


def format_actionability_requirements_for_prompt() -> str:
    """Describe kind-specific field requirements for the review system prompt."""
    lines = [
        "Each annotation must include kind-specific fields:",
        "- missing_section: non-empty message and suggestion",
        "- inconsistency: non-empty message and location (section-scoped)",
        "- conciseness: non-empty message, suggestion, and location",
    ]
    return "\n".join(lines)
