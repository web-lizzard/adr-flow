"""Pydantic wire models and mapping for LLM review structured output."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)


class ReviewAnnotationPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ReviewAnnotationKind = Field(description="Annotation category")
    message: str = Field(description="Human-readable finding")
    location: str | None = Field(
        default=None,
        description="Section reference, e.g. ## Context",
    )
    suggestion: str | None = Field(
        default=None,
        description="Actionable fix for missing_section or conciseness",
    )


class ReviewPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    annotations: tuple[ReviewAnnotationPayload, ...] = Field(
        description="List of review findings for the ADR",
    )


def to_review_result(
    payload: ReviewPayload,
    *,
    markdown: str,
    reviewed_at: datetime,
) -> ReviewResult:
    """Map validated wire payload to domain ReviewResult."""
    annotations = tuple(
        ReviewAnnotation(
            kind=item.kind,
            message=item.message,
            location=item.location,
            suggestion=item.suggestion,
        )
        for item in payload.annotations
    )
    return ReviewResult(
        annotations=annotations,
        reviewed_at=reviewed_at,
        reviewed_content=markdown,
    )
