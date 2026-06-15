from typing import Protocol
from uuid import UUID


class EventStore(Protocol):
    async def append(
        self,
        events: list,
        aggregate_id: UUID,
        aggregate_type: str,
    ) -> None: ...
