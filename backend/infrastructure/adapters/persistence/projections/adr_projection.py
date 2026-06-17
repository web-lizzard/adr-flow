"""ADR projection write adapter."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.adr_projection import AdrProjection
from application.review_metadata import ReviewErrorMetadata
from domain.adr.aggregate import ADR
from domain.adr.value_objects import AdrStatus, ReviewResult
from infrastructure.adapters.persistence.models import Adr


class SqlAdrProjection(AdrProjection):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, adr: ADR) -> None:
        self._session.add(_to_orm_row(adr))

    async def update_content(self, adr: ADR) -> None:
        await self._session.execute(
            update(Adr)
            .where(Adr.id == adr.adr_id.value)
            .values(
                title=adr.title.value,
                content=adr.content.value,
                updated_at=adr.updated_at,
            )
        )

    async def mark_in_review(self, adr_id: UUID, *, updated_at: datetime) -> None:
        await self._session.execute(
            update(Adr)
            .where(Adr.id == adr_id)
            .values(
                status=AdrStatus.IN_REVIEW.value,
                review_annotations=None,
                reviewed_at=None,
                review_error=None,
                updated_at=updated_at,
            )
        )

    async def apply_review_result(
        self,
        adr_id: UUID,
        *,
        review_result: ReviewResult,
        updated_at: datetime,
    ) -> None:
        await self._session.execute(
            update(Adr)
            .where(Adr.id == adr_id)
            .values(
                status=AdrStatus.AFTER_REVIEW.value,
                review_annotations=review_result.model_dump(mode="json"),
                reviewed_at=review_result.reviewed_at,
                review_error=None,
                updated_at=updated_at,
            )
        )

    async def record_review_failure(
        self,
        adr_id: UUID,
        *,
        review_error: ReviewErrorMetadata,
        updated_at: datetime,
    ) -> None:
        await self._session.execute(
            update(Adr)
            .where(Adr.id == adr_id)
            .values(
                review_error={
                    "source_event_id": str(review_error.source_event_id),
                    "code": review_error.code,
                    "message": review_error.message,
                    "failed_at": review_error.failed_at.isoformat(),
                },
                updated_at=updated_at,
            )
        )


def _to_orm_row(adr: ADR) -> Adr:
    return Adr(
        id=adr.adr_id.value,
        user_id=adr.user_id.value,
        title=adr.title.value,
        content=adr.content.value,
        status=adr.status.value,
        review_annotations=_review_annotations(adr),
        is_deleted=adr.is_deleted,
        created_at=adr.created_at,
        updated_at=adr.updated_at,
        reviewed_at=adr.reviewed_at,
        review_error=None,
    )


def _review_annotations(adr: ADR) -> dict | list | None:
    if adr.review_result is None:
        return None
    return adr.review_result.model_dump(mode="json")
