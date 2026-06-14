from dataclasses import dataclass
from datetime import datetime

from domain.adr.value_objects import (
    AdrContent,
    AdrId,
    AdrStatus,
    AdrTitle,
    ReviewResult,
)
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class ADR:
    adr_id: AdrId
    user_id: UserId
    title: AdrTitle
    content: AdrContent
    status: AdrStatus
    review_result: ReviewResult | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None
