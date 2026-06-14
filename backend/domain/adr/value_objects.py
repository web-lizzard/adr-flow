from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AdrStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    AFTER_REVIEW = "after_review"
    PROPOSED = "proposed"


@dataclass(frozen=True, slots=True)
class AdrId:
    value: UUID


@dataclass(frozen=True, slots=True)
class AdrTitle:
    value: str


@dataclass(frozen=True, slots=True)
class AdrContent:
    value: str


class ReviewAnnotationKind(StrEnum):
    MISSING_SECTION = "missing_section"
    INCONSISTENCY = "inconsistency"
    CONCISENESS = "conciseness"


@dataclass(frozen=True, slots=True)
class ReviewAnnotation:
    kind: ReviewAnnotationKind
    message: str
    location: str | None = None
    suggestion: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewResult:
    annotations: tuple[ReviewAnnotation, ...]
    reviewed_at: datetime
    reviewed_content: str | None = None
