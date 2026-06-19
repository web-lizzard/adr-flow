"""Shared fakes for command handler unit tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from application.ports.event_store import StoredEvent
from domain.adr import (
    ADRCreated,
    ADRSubmittedForReview,
    AIReviewCompleted,
    AIReviewFailed,
    AdrContent,
    AdrId,
    AdrTitle,
)
from domain.adr.value_objects import ReviewResult
from domain.user.value_objects import UserId


class FakeEventStore:
    def __init__(
        self,
        *,
        streams: dict[tuple[UUID, str], list[StoredEvent]] | None = None,
    ) -> None:
        self.appended: list[tuple[list, UUID, str]] = []
        self.marked_processed: list[tuple[UUID, datetime]] = []
        self._streams = streams or {}
        self.load_stream_calls: list[tuple[UUID, str]] = []

    async def append(
        self, events: list, aggregate_id: UUID, aggregate_type: str
    ) -> list[StoredEvent]:
        self.appended.append((events, aggregate_id, aggregate_type))
        return [
            StoredEvent(
                id=uuid4(),
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event=event,
                occurred_at=event.occurred_at,
            )
            for event in events
        ]

    async def load_stream(
        self, aggregate_id: UUID, aggregate_type: str
    ) -> list[StoredEvent]:
        self.load_stream_calls.append((aggregate_id, aggregate_type))
        return list(self._streams.get((aggregate_id, aggregate_type), []))

    async def load_unprocessed(self, *, limit: int = 100) -> list[StoredEvent]:
        return []

    async def mark_processed(self, event_id: UUID, *, processed_at: datetime) -> None:
        self.marked_processed.append((event_id, processed_at))


class FakeUnitOfWork:
    def __init__(self, *, event_store: FakeEventStore | None = None) -> None:
        self.event_store = event_store or FakeEventStore()
        self.adr_projection = FakeAdrProjection()
        self.user_projection = FakeUserProjection()
        self.locked_aggregates: list[UUID] = []

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def lock_aggregate(self, aggregate_id: UUID) -> None:
        self.locked_aggregates.append(aggregate_id)


class FakeUnitOfWorkFactory:
    def __init__(self, *, event_store: FakeEventStore | None = None) -> None:
        self._event_store = event_store
        self.unit_of_works: list[FakeUnitOfWork] = []

    @asynccontextmanager
    async def begin(self):
        uow = FakeUnitOfWork(event_store=self._event_store)
        self.unit_of_works.append(uow)
        yield uow


class FakeAdrProjection:
    def __init__(self) -> None:
        self.inserted: list = []
        self.updated: list = []
        self.marked_in_review: list[tuple[UUID, datetime]] = []
        self.marked_proposed: list[tuple[UUID, datetime]] = []
        self.applied_results: list[tuple[UUID, ReviewResult, datetime]] = []
        self.recorded_failures: list = []

    async def insert(self, adr) -> None:
        self.inserted.append(adr)

    async def update_content(self, adr) -> None:
        self.updated.append(adr)

    async def mark_in_review(self, adr_id: UUID, *, updated_at: datetime) -> None:
        self.marked_in_review.append((adr_id, updated_at))

    async def mark_proposed(self, adr_id: UUID, *, updated_at: datetime) -> bool:
        self.marked_proposed.append((adr_id, updated_at))
        return True

    async def apply_review_result(
        self,
        adr_id: UUID,
        *,
        review_result: ReviewResult,
        updated_at: datetime,
    ) -> None:
        self.applied_results.append((adr_id, review_result, updated_at))

    async def record_review_failure(
        self,
        adr_id: UUID,
        *,
        review_error,
        updated_at: datetime,
    ) -> None:
        self.recorded_failures.append((adr_id, review_error, updated_at))


class FakeUserProjection:
    def __init__(self) -> None:
        self.inserted: list[tuple[UUID, str, str, datetime]] = []

    async def insert(
        self,
        *,
        user_id: UUID,
        email: str,
        password_hash: str,
        created_at: datetime,
    ) -> None:
        self.inserted.append((user_id, email, password_hash, created_at))


def adr_created_stream(
    *,
    adr_id: UUID,
    user_id: UUID,
    title: str = "My ADR",
    content: str = "## Context",
    occurred_at: datetime | None = None,
    extra_events: list | None = None,
) -> list[StoredEvent]:
    when = occurred_at or datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    created = ADRCreated(
        adr_id=AdrId(adr_id),
        user_id=UserId(user_id),
        title=AdrTitle(title),
        content=AdrContent(content),
        occurred_at=when,
    )
    events = [created, *(extra_events or [])]
    return [
        StoredEvent(
            id=uuid4(),
            aggregate_type="adr",
            aggregate_id=adr_id,
            event=event,
            occurred_at=event.occurred_at,
        )
        for event in events
    ]


def in_review_stream(
    *,
    adr_id: UUID,
    user_id: UUID,
    title: str = "My ADR",
    content: str = "## Context",
    submit_event_id: UUID | None = None,
    occurred_at: datetime | None = None,
) -> list[StoredEvent]:
    """Event stream ending in ``in_review`` (created + submitted)."""
    when = occurred_at or datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    submit_at = datetime(2026, 6, 16, 11, 0, tzinfo=UTC)
    stream = adr_created_stream(
        adr_id=adr_id,
        user_id=user_id,
        title=title,
        content=content,
        occurred_at=when,
    )
    submit = ADRSubmittedForReview(
        adr_id=AdrId(adr_id),
        user_id=UserId(user_id),
        content=AdrContent(content),
        occurred_at=submit_at,
    )
    stream.append(
        StoredEvent(
            id=submit_event_id or uuid4(),
            aggregate_type="adr",
            aggregate_id=adr_id,
            event=submit,
            occurred_at=submit_at,
        )
    )
    return stream


def after_review_stream(
    *,
    adr_id: UUID,
    user_id: UUID,
    content: str,
    review_result: ReviewResult,
    submit_event_id: UUID | None = None,
) -> list[StoredEvent]:
    """Event stream with completed AI review (``after_review``)."""
    stream = in_review_stream(
        adr_id=adr_id,
        user_id=user_id,
        content=content,
        submit_event_id=submit_event_id,
    )
    completed_at = review_result.reviewed_at
    stream.append(
        StoredEvent(
            id=uuid4(),
            aggregate_type="adr",
            aggregate_id=adr_id,
            event=AIReviewCompleted(
                adr_id=AdrId(adr_id),
                review_result=review_result,
                occurred_at=completed_at,
            ),
            occurred_at=completed_at,
        )
    )
    return stream


def stream_with_review_failure(
    *,
    adr_id: UUID,
    user_id: UUID,
    content: str,
    source_event_id: UUID,
    message: str = "Already failed",
) -> list[StoredEvent]:
    """Event stream with ``AIReviewFailed`` tied to a submit event."""
    stream = in_review_stream(
        adr_id=adr_id,
        user_id=user_id,
        content=content,
        submit_event_id=source_event_id,
    )
    failed_at = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)
    stream.append(
        StoredEvent(
            id=uuid4(),
            aggregate_type="adr",
            aggregate_id=adr_id,
            event=AIReviewFailed(
                adr_id=AdrId(adr_id),
                source_event_id=source_event_id,
                code="validation_failed",
                message=message,
                occurred_at=failed_at,
            ),
            occurred_at=failed_at,
        )
    )
    return stream
