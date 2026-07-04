from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from domain.adr.required_sections import SectionName


class AdrStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    AFTER_REVIEW = "after_review"
    PROPOSED = "proposed"
    REVIEW_FAILED = "review_failed"


class AdrId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    def __init__(self, value: UUID) -> None:
        super().__init__(value=value)


class AdrTitle(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    def __init__(self, value: str) -> None:
        super().__init__(value=value)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = "ADR title is required"
            raise ValueError(msg)
        return normalized


class AdrContent(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    def __init__(self, value: str) -> None:
        super().__init__(value=value)


class ReviewAnnotationKind(StrEnum):
    MISSING_SECTION = "missing_section"
    INCONSISTENCY = "inconsistency"
    CONCISENESS = "conciseness"


class ReviewAnnotation(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: ReviewAnnotationKind
    message: str
    location: str | None = None
    suggestion: str | None = None


class SectionRating(BaseModel):
    model_config = ConfigDict(frozen=True)

    section: SectionName
    score: int
    feedback: str = ""

    @field_validator("score")
    @classmethod
    def validate_score(cls, score: int) -> int:
        if score < 0 or score > 5:
            msg = "Section rating score must be between 0 and 5"
            raise ValueError(msg)
        return score

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, feedback: str, info: ValidationInfo) -> str:
        score = info.data.get("score")
        if score is not None and score >= 1 and not feedback.strip():
            msg = "Section rating feedback is required when score is at least 1"
            raise ValueError(msg)
        return feedback


class ReviewResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    annotations: tuple[ReviewAnnotation, ...]
    reviewed_at: datetime
    reviewed_content: str | None = None
    section_ratings: tuple[SectionRating, ...] = ()


class ReviewError(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    message: str
