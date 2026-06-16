"""Pydantic request/response models for ADR endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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


class AdrResponse(BaseModel):
    id: UUID
    title: str
    content: str
    status: str
    created_at: datetime
    updated_at: datetime


class CreateAdrResponse(BaseModel):
    id: UUID


class AdrSummary(BaseModel):
    id: UUID
    title: str
    status: str
    updated_at: datetime


class SearchAdrsResponse(BaseModel):
    results: list[AdrSummary]
