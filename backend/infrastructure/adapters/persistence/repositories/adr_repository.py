"""ADR read repository adapter."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.adr_repository import AdrReadModel, AdrRepository
from infrastructure.adapters.persistence.models import Adr


class SqlAdrRepository(AdrRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_by_id_for_owner(
        self, adr_id: UUID, user_id: UUID
    ) -> AdrReadModel | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Adr).where(
                    Adr.id == adr_id,
                    Adr.user_id == user_id,
                    Adr.is_deleted.is_(False),
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _to_read_model(row)

    async def find_by_title_for_owner(
        self, title: str, user_id: UUID
    ) -> AdrReadModel | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Adr).where(
                    func.lower(Adr.title) == title.lower(),
                    Adr.user_id == user_id,
                    Adr.is_deleted.is_(False),
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _to_read_model(row)

    async def search_by_title(self, user_id: UUID, query: str) -> list[AdrReadModel]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Adr).where(
                    Adr.user_id == user_id,
                    Adr.is_deleted.is_(False),
                    Adr.title.ilike(f"%{query}%"),
                )
            )
            rows = result.scalars().all()
            return [_to_read_model(row) for row in rows]


def _to_read_model(row: Adr) -> AdrReadModel:
    return AdrReadModel(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        content=row.content,
        status=row.status,
        is_deleted=row.is_deleted,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
