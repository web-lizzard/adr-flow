"""Deterministic fake LLM reviewer for local development and tests."""

from datetime import UTC, datetime

from domain.adr import find_missing_or_empty_sections
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)


class FakeReviewer:
    async def review(self, markdown: str) -> ReviewResult:
        missing = find_missing_or_empty_sections(markdown)
        annotations: list[ReviewAnnotation] = []
        for section in sorted(missing, key=lambda item: item.value):
            annotations.append(
                ReviewAnnotation(
                    kind=ReviewAnnotationKind.MISSING_SECTION,
                    message=f"Missing {section.value} section",
                    location=f"## {section.value}",
                    suggestion=f"Add content for the {section.value} section.",
                )
            )

        if "## Decision" in markdown and "## Status" in markdown:
            annotations.append(
                ReviewAnnotation(
                    kind=ReviewAnnotationKind.INCONSISTENCY,
                    message="Status may not reflect the recorded decision.",
                    location="## Status",
                )
            )

        if len(markdown) > 500:
            annotations.append(
                ReviewAnnotation(
                    kind=ReviewAnnotationKind.CONCISENESS,
                    message="ADR body is longer than needed for an MVP draft.",
                    location="## Context",
                    suggestion="Trim background detail to the decision-critical facts.",
                )
            )

        return ReviewResult(
            annotations=tuple(annotations),
            reviewed_at=datetime.now(UTC),
            reviewed_content=markdown,
        )
