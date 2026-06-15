"""Users projection write adapter."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.user_projection import UserProjection
from infrastructure.adapters.persistence.models import User


class SqlUserProjection(UserProjection):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        user_id: UUID,
        email: str,
        password_hash: str,
        created_at: datetime,
    ) -> None:
        self._session.add(
            User(
                id=user_id,
                email=email,
                password_hash=password_hash,
                created_at=created_at,
            )
        )
