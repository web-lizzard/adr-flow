from dataclasses import dataclass
from datetime import datetime

from domain.adr.value_objects import AdrContent, AdrId, AdrTitle, ReviewResult
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class ADRCreated:
    adr_id: AdrId
    user_id: UserId
    title: AdrTitle
    content: AdrContent
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ADRContentUpdated:
    adr_id: AdrId
    content: AdrContent
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ADRSubmittedForReview:
    adr_id: AdrId
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AIReviewCompleted:
    adr_id: AdrId
    review_result: ReviewResult
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ADRPublished:
    adr_id: AdrId
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ADRSoftDeleted:
    adr_id: AdrId
    occurred_at: datetime
