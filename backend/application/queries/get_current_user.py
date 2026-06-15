from dataclasses import dataclass
from uuid import UUID

from application.ports.user_repository import UserReadModel, UserRepository
from domain.errors import UserNotFound


@dataclass(frozen=True, slots=True)
class GetCurrentUserQuery:
    user_id: UUID


class GetCurrentUserQueryHandler:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def handle(self, query: GetCurrentUserQuery) -> UserReadModel:
        user = await self._user_repository.find_by_id(query.user_id)
        if user is None:
            raise UserNotFound()
        return user
