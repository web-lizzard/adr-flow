from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserReadModel:
    id: UUID
    email: str
    password_hash: str
    created_at: datetime


class UserRepository(Protocol):
    async def find_by_email(self, email: str) -> UserReadModel | None: ...

    async def find_by_id(self, user_id: UUID) -> UserReadModel | None: ...
