from uuid import UUID
from typing import Any, cast

from pydantic import model_validator

from domain.adr.value_objects import AdrContent, AdrId, AdrTitle, ReviewResult
from domain.events import DomainEvent
from domain.user.value_objects import UserId


class ADRCreated(DomainEvent):
    adr_id: AdrId
    user_id: UserId
    title: AdrTitle
    content: AdrContent


class ADRContentUpdated(DomainEvent):
    adr_id: AdrId
    content: AdrContent
    title: AdrTitle | None = None


class ADRSubmittedForReview(DomainEvent):
    adr_id: AdrId
    user_id: UserId
    content: AdrContent


class AIReviewCompleted(DomainEvent):
    adr_id: AdrId
    review_result: ReviewResult


class AIReviewFailed(DomainEvent):
    adr_id: AdrId
    source_event_id: UUID
    message: str
    kind: str = "adr_review_failed_error"

    @model_validator(mode="before")
    @classmethod
    def _legacy_code_to_kind(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = cast(dict[str, Any], data)
        if "kind" in payload or "code" not in payload:
            return data
        legacy_code = payload["code"]
        if not isinstance(legacy_code, str):
            return data
        return {**payload, "kind": legacy_code}


class ADRPublished(DomainEvent):
    adr_id: AdrId


class ADRSoftDeleted(DomainEvent):
    adr_id: AdrId
