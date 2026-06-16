from dataclasses import dataclass
from uuid import UUID

from application.ports.adr_repository import AdrReadModel, AdrRepository


@dataclass(frozen=True, slots=True)
class SearchAdrsByTitleQuery:
    user_id: UUID
    query: str


class SearchAdrsByTitleQueryHandler:
    def __init__(self, adr_repository: AdrRepository) -> None:
        self._adr_repository = adr_repository

    async def handle(self, query: SearchAdrsByTitleQuery) -> list[AdrReadModel]:
        return await self._adr_repository.search_by_title(query.user_id, query.query)
