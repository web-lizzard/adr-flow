from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class AdrStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    AFTER_REVIEW = "after_review"
    PROPOSED = "proposed"


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


class ReviewResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    annotations: tuple[ReviewAnnotation, ...]
    reviewed_at: datetime
    reviewed_content: str | None = None
