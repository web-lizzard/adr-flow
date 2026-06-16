from dataclasses import dataclass
from uuid import UUID

from application.ports.adr_repository import AdrReadModel, AdrRepository


@dataclass(frozen=True, slots=True)
class ListAdrsQuery:
    user_id: UUID
    limit: int = 50
    offset: int = 0


class ListAdrsQueryHandler:
    def __init__(self, adr_repository: AdrRepository) -> None:
        self._adr_repository = adr_repository

    async def handle(self, query: ListAdrsQuery) -> list[AdrReadModel]:
        return await self._adr_repository.list_for_owner(
            query.user_id,
            limit=query.limit,
            offset=query.offset,
        )
