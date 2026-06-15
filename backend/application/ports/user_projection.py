from datetime import datetime
from typing import Protocol
from uuid import UUID


class UserProjection(Protocol):
    async def insert(
        self,
        user_id: UUID,
        email: str,
        password_hash: str,
        created_at: datetime,
    ) -> None: ...
