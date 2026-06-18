"""Event store port for append and async replay."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.events import DomainEvent


@dataclass(frozen=True, slots=True)
class StoredEvent:
    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event: DomainEvent
    occurred_at: datetime


class EventStore(Protocol):
    async def append(
        self,
        events: list,
        aggregate_id: UUID,
        aggregate_type: str,
    ) -> list[StoredEvent]: ...

    async def load_unprocessed(self, *, limit: int = 100) -> list[StoredEvent]: ...

    async def load_stream(
        self, aggregate_id: UUID, aggregate_type: str
    ) -> list[StoredEvent]: ...

    async def mark_processed(
        self, event_id: UUID, *, processed_at: datetime
    ) -> None: ...

    async def mark_sync_projection_events_processed(
        self, *, processed_at: datetime
    ) -> None: ...
