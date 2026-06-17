from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.review_metadata import ReviewErrorMetadata
from domain.adr.value_objects import ReviewResult


@dataclass(frozen=True, slots=True)
class AdrReadModel:
    id: UUID
    user_id: UUID
    title: str
    content: str
    status: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    review_annotations: ReviewResult | None = None
    reviewed_at: datetime | None = None
    review_error: ReviewErrorMetadata | None = None


class AdrRepository(Protocol):
    async def find_by_id_for_owner(
        self, adr_id: UUID, user_id: UUID
    ) -> AdrReadModel | None: ...

    async def find_by_title_for_owner(
        self, title: str, user_id: UUID
    ) -> AdrReadModel | None: ...

    async def search_by_title(
        self, user_id: UUID, query: str
    ) -> list[AdrReadModel]: ...

    async def list_for_owner(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdrReadModel]: ...
