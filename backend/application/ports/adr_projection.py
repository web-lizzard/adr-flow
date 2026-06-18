from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.review_metadata import ReviewErrorMetadata
from domain.adr.aggregate import ADR
from domain.adr.value_objects import ReviewResult


class AdrProjection(Protocol):
    async def insert(self, adr: ADR) -> None: ...

    async def update_content(self, adr: ADR) -> None: ...

    async def mark_in_review(self, adr_id: UUID, *, updated_at: datetime) -> None: ...

    async def mark_proposed(self, adr_id: UUID, *, updated_at: datetime) -> bool: ...

    async def apply_review_result(
        self,
        adr_id: UUID,
        *,
        review_result: ReviewResult,
        updated_at: datetime,
    ) -> None: ...

    async def record_review_failure(
        self,
        adr_id: UUID,
        *,
        review_error: ReviewErrorMetadata,
        updated_at: datetime,
    ) -> None: ...
