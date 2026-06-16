from dataclasses import dataclass
from uuid import UUID

from application.ports.adr_repository import AdrReadModel, AdrRepository
from domain.errors import AdrNotFound


@dataclass(frozen=True, slots=True)
class GetAdrQuery:
    adr_id: UUID
    user_id: UUID


class GetAdrQueryHandler:
    def __init__(self, adr_repository: AdrRepository) -> None:
        self._adr_repository = adr_repository

    async def handle(self, query: GetAdrQuery) -> AdrReadModel:
        adr = await self._adr_repository.find_by_id_for_owner(
            query.adr_id,
            query.user_id,
        )
        if adr is None:
            raise AdrNotFound()
        return adr
