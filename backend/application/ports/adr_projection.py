from typing import Protocol

from domain.adr.aggregate import ADR


class AdrProjection(Protocol):
    async def insert(self, adr: ADR) -> None: ...

    async def update_content(self, adr: ADR) -> None: ...
