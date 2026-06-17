"""Pydantic request/response models for ADR endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from application.review_metadata import ReviewErrorMetadata
from domain.adr.value_objects import ReviewAnnotationKind, ReviewResult


class CreateAdrRequest(BaseModel):
    title: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            msg = "ADR title is required"
            raise ValueError(msg)
        return title


class UpdateAdrRequest(BaseModel):
    title: str | None = None
    content: str | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        if not title:
            msg = "ADR title is required"
            raise ValueError(msg)
        return title


class ReviewAnnotationResponse(BaseModel):
    kind: ReviewAnnotationKind
    message: str
    location: str | None = None
    suggestion: str | None = None


class ReviewErrorResponse(BaseModel):
    source_event_id: UUID
    code: str
    message: str
    failed_at: datetime

    @classmethod
    def from_metadata(cls, metadata: ReviewErrorMetadata) -> "ReviewErrorResponse":
        return cls(
            source_event_id=metadata.source_event_id,
            code=metadata.code,
            message=metadata.message,
            failed_at=metadata.failed_at,
        )


class AdrResponse(BaseModel):
    id: UUID
    title: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime
    review_annotations: list[ReviewAnnotationResponse] | None = None
    reviewed_at: datetime | None = None
    review_error: ReviewErrorResponse | None = None


class ReviewStatusResponse(BaseModel):
    status: str
    reviewed_at: datetime | None = None
    review_error: ReviewErrorResponse | None = None
    annotation_counts: dict[str, int] | None = None


class CreateAdrResponse(BaseModel):
    id: UUID


class AdrSummary(BaseModel):
    id: UUID
    title: str
    status: str
    updated_at: datetime


class SearchAdrsResponse(BaseModel):
    results: list[AdrSummary]


class ListAdrsResponse(BaseModel):
    results: list[AdrSummary]


def annotation_counts_from_result(
    review_result: ReviewResult | None,
) -> dict[str, int] | None:
    if review_result is None:
        return None
    counts: dict[str, int] = {}
    for annotation in review_result.annotations:
        kind = annotation.kind.value
        counts[kind] = counts.get(kind, 0) + 1
    return counts
