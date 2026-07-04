"""Phase 0 static gap detection and score-0 ratings."""

from domain.adr.required_sections import find_missing_or_empty_sections
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    SectionRating,
)


def synthesize_static_review(
    markdown: str,
) -> tuple[tuple[ReviewAnnotation, ...], tuple[SectionRating, ...]]:
    """Return static missing_section annotations and score-0 ratings for gaps."""
    gaps = find_missing_or_empty_sections(markdown)
    if not gaps:
        return (), ()

    annotations: list[ReviewAnnotation] = []
    ratings: list[SectionRating] = []

    for section in sorted(gaps, key=lambda item: item.value):
        location = f"## {section.value}"
        annotations.append(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message=(
                    f"The {section.value} section is missing, empty, or placeholder-only."
                ),
                location=location,
                suggestion=(
                    f"Add substantive content for the {section.value} section."
                ),
            )
        )
        ratings.append(
            SectionRating(section=section, score=0, feedback=""),
        )

    return tuple(annotations), tuple(ratings)
