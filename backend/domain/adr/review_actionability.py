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


def format_actionability_requirements_for_prompt(
    *,
    kinds: tuple[ReviewAnnotationKind, ...] | None = None,
) -> str:
    """Describe kind-specific field requirements for the review system prompt."""
    selected = kinds if kinds is not None else tuple(ReviewAnnotationKind)
    kind_lines = {
        ReviewAnnotationKind.MISSING_SECTION: (
            "- missing_section: non-empty message and suggestion"
        ),
        ReviewAnnotationKind.INCONSISTENCY: (
            "- inconsistency: non-empty message and location (section-scoped)"
        ),
        ReviewAnnotationKind.CONCISENESS: (
            "- conciseness: non-empty message, suggestion, and location"
        ),
    }
    lines = ["Each annotation must include kind-specific fields:"]
    lines.extend(kind_lines[kind] for kind in selected)
    return "\n".join(lines)
