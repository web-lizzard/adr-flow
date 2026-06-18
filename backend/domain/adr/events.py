from uuid import UUID

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
    code: str
    message: str


class ADRPublished(DomainEvent):
    adr_id: AdrId


class ADRSoftDeleted(DomainEvent):
    adr_id: AdrId
