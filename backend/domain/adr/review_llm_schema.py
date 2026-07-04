"""Pydantic wire models and mapping for LLM review structured output."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domain.adr.required_sections import SectionName
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
    SectionRating,
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


class SectionReviewPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: SectionName
    score: int = Field(ge=1, le=5)
    feedback: str
    annotations: tuple[ReviewAnnotationPayload, ...] = ()

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, feedback: str) -> str:
        if not feedback.strip():
            msg = "Section review feedback is required"
            raise ValueError(msg)
        return feedback

    @field_validator("annotations")
    @classmethod
    def validate_annotations(
        cls,
        annotations: tuple[ReviewAnnotationPayload, ...],
    ) -> tuple[ReviewAnnotationPayload, ...]:
        for annotation in annotations:
            if annotation.kind is ReviewAnnotationKind.MISSING_SECTION:
                msg = "Section review payloads must not include missing_section annotations"
                raise ValueError(msg)
        return annotations


class CrossSectionReviewPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    annotations: tuple[ReviewAnnotationPayload, ...] = ()


def _payload_to_annotation(payload: ReviewAnnotationPayload) -> ReviewAnnotation:
    return ReviewAnnotation(
        kind=payload.kind,
        message=payload.message,
        location=payload.location,
        suggestion=payload.suggestion,
    )


def to_review_result(
    payload: ReviewPayload,
    *,
    markdown: str,
    reviewed_at: datetime,
) -> ReviewResult:
    """Map validated wire payload to domain ReviewResult."""
    annotations = tuple(_payload_to_annotation(item) for item in payload.annotations)
    return ReviewResult(
        annotations=annotations,
        reviewed_at=reviewed_at,
        reviewed_content=markdown,
    )


def merge_review_results(
    static_annotations: tuple[ReviewAnnotation, ...],
    static_ratings: tuple[SectionRating, ...],
    section_payloads: tuple[SectionReviewPayload, ...],
    cross_payload: CrossSectionReviewPayload,
    *,
    markdown: str,
    reviewed_at: datetime,
) -> ReviewResult:
    """Merge static Phase 0 output and parallel LLM payloads into ReviewResult."""
    llm_annotations: list[ReviewAnnotation] = []
    for section_payload in section_payloads:
        llm_annotations.extend(
            _payload_to_annotation(annotation)
            for annotation in section_payload.annotations
        )
    llm_annotations.extend(
        _payload_to_annotation(annotation) for annotation in cross_payload.annotations
    )

    ratings_by_section: dict[SectionName, SectionRating] = {
        rating.section: rating for rating in static_ratings
    }
    for section_payload in section_payloads:
        ratings_by_section[section_payload.section] = SectionRating(
            section=section_payload.section,
            score=section_payload.score,
            feedback=section_payload.feedback,
        )

    section_ratings = tuple(ratings_by_section[section] for section in SectionName)

    return ReviewResult(
        annotations=(*static_annotations, *llm_annotations),
        section_ratings=section_ratings,
        reviewed_at=reviewed_at,
        reviewed_content=markdown,
    )
