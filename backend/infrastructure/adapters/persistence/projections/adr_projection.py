"""ADR projection write adapter."""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.adr_projection import AdrProjection
from domain.adr.aggregate import ADR
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
    )


def _review_annotations(adr: ADR) -> dict | list | None:
    if adr.review_result is None:
        return None
    return adr.review_result.model_dump()
