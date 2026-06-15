"""Users read repository adapter."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.user_repository import UserReadModel, UserRepository
from infrastructure.adapters.persistence.models import User


class SqlUserRepository(UserRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_by_email(self, email: str) -> UserReadModel | None:
        async with self._session_factory() as session:
            result = await session.execute(select(User).where(User.email == email))
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _to_read_model(row)

    async def find_by_id(self, user_id: UUID) -> UserReadModel | None:
        async with self._session_factory() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _to_read_model(row)


def _to_read_model(row: User) -> UserReadModel:
    return UserReadModel(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        created_at=row.created_at,
    )
