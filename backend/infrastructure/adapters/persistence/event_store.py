"""Append-only event store adapter."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.event_store import EventStore, StoredEvent
from domain.adr.events import (
    ADRContentUpdated,
    ADRCreated,
    ADRPublished,
    ADRSoftDeleted,
    ADRSubmittedForReview,
    AIReviewCompleted,
    AIReviewFailed,
)
from domain.events import DomainEvent
from infrastructure.adapters.persistence.models import Event

_EVENT_TYPES: dict[str, type[DomainEvent]] = {
    "ADRCreated": ADRCreated,
    "ADRContentUpdated": ADRContentUpdated,
    "ADRSubmittedForReview": ADRSubmittedForReview,
    "AIReviewCompleted": AIReviewCompleted,
    "AIReviewFailed": AIReviewFailed,
    "ADRPublished": ADRPublished,
    "ADRSoftDeleted": ADRSoftDeleted,
}


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

    async def load_unprocessed(self, *, limit: int = 100) -> list[StoredEvent]:
        result = await self._session.execute(
            select(Event)
            .where(Event.processed_at.is_(None))
            .order_by(Event.occurred_at.asc(), Event.id.asc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [_to_stored_event(row) for row in rows]

    async def mark_processed(self, event_id: UUID, *, processed_at: datetime) -> None:
        await self._session.execute(
            update(Event).where(Event.id == event_id).values(processed_at=processed_at)
        )


def _serialize_event(event: DomainEvent) -> tuple[str, dict[str, Any], datetime]:
    event_type = type(event).__name__
    payload = event.model_dump(mode="json")
    return event_type, payload, event.occurred_at


def _to_stored_event(row: Event) -> StoredEvent:
    event_cls = _EVENT_TYPES.get(row.event_type)
    if event_cls is None:
        msg = f"Unknown event type: {row.event_type}"
        raise ValueError(msg)
    event = event_cls.model_validate(row.payload)
    return StoredEvent(
        id=row.id,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        event=event,
        occurred_at=row.occurred_at,
    )
