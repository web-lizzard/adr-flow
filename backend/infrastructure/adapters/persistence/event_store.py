"""Append-only event store adapter."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.event_store import EventStore
from domain.events import DomainEvent
from infrastructure.adapters.persistence.models import Event


class SqlEventStore(EventStore):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        events: list,
        aggregate_id: UUID,
        aggregate_type: str,
    ) -> None:
        if not events:
            return

        for event in events:
            event_type, payload, occurred_at = _serialize_event(event)
            self._session.add(
                Event(
                    id=uuid4(),
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    event_type=event_type,
                    payload=payload,
                    occurred_at=occurred_at,
                    processed_at=None,
                )
            )


def _serialize_event(event: DomainEvent) -> tuple[str, dict[str, Any], datetime]:
    event_type = type(event).__name__
    payload = event.model_dump(mode="json")
    return event_type, payload, event.occurred_at
