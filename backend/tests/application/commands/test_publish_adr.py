"""PublishAdr command handler tests."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from application.commands.publish_adr import PublishAdrCommand, PublishAdrCommandHandler
from application.ports.adr_repository import AdrReadModel
from application.ports.event_store import StoredEvent
from domain.adr import ADRPublished, AdrStatus
from domain.errors import AdrInvalidPublishStatus, AdrNotFound


class FakeEventStore:
    def __init__(self) -> None:
        self.appended: list[tuple[list, UUID, str]] = []
        self.marked_processed: list[tuple[UUID, datetime]] = []

    async def append(
        self, events: list, aggregate_id: UUID, aggregate_type: str
    ) -> list[StoredEvent]:
        self.appended.append((events, aggregate_id, aggregate_type))
        stored: list[StoredEvent] = []
        for event in events:
            stored.append(
                StoredEvent(
                    id=uuid4(),
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    event=event,
                    occurred_at=event.occurred_at,
                )
            )
        return stored

    async def load_unprocessed(self, *, limit: int = 100) -> list[StoredEvent]:
        return []

    async def mark_processed(self, event_id: UUID, *, processed_at: datetime) -> None:
        self.marked_processed.append((event_id, processed_at))


class FakeAdrProjection:
    def __init__(self) -> None:
        self.marked_proposed: list[tuple[UUID, datetime]] = []

    async def insert(self, adr) -> None:
        return None

    async def update_content(self, adr) -> None:
        return None

    async def mark_in_review(self, adr_id: UUID, *, updated_at: datetime) -> None:
        return None

    async def mark_proposed(self, adr_id: UUID, *, updated_at: datetime) -> bool:
        self.marked_proposed.append((adr_id, updated_at))
        return True

    async def apply_review_result(self, adr_id, *, review_result, updated_at) -> None:
        return None

    async def record_review_failure(self, adr_id, *, review_error, updated_at) -> None:
        return None


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.event_store = FakeEventStore()
        self.adr_projection = FakeAdrProjection()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeUnitOfWorkFactory:
    def __init__(self) -> None:
        self.unit_of_works: list[FakeUnitOfWork] = []

    @asynccontextmanager
    async def begin(self):
        uow = FakeUnitOfWork()
        self.unit_of_works.append(uow)
        yield uow


class FakeAdrRepository:
    def __init__(self, *, by_id: AdrReadModel | None = None) -> None:
        self._by_id = by_id

    async def find_by_id_for_owner(
        self, adr_id: UUID, user_id: UUID
    ) -> AdrReadModel | None:
        if self._by_id is None:
            return None
        if self._by_id.id != adr_id or self._by_id.user_id != user_id:
            return None
        return self._by_id

    async def find_by_title_for_owner(
        self, title: str, user_id: UUID
    ) -> AdrReadModel | None:
        return None

    async def search_by_title(self, user_id: UUID, query: str) -> list[AdrReadModel]:
        return []

    async def list_for_owner(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdrReadModel]:
        return []


def _adr_read_model(
    *,
    adr_id: UUID,
    user_id: UUID,
    content: str = "## Context\n\nReviewed body",
    status: str = "after_review",
) -> AdrReadModel:
    now = datetime(2026, 6, 17, 10, 0, tzinfo=UTC)
    return AdrReadModel(
        id=adr_id,
        user_id=user_id,
        title="Publish ADR",
        content=content,
        status=status,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )


def test_publish_adr_emits_event_marks_proposed_and_marks_processed() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    repository = FakeAdrRepository(
        by_id=_adr_read_model(adr_id=adr_id, user_id=user_id)
    )
    uow_factory = FakeUnitOfWorkFactory()
    handler = PublishAdrCommandHandler(uow_factory, repository)

    asyncio.run(handler.handle(PublishAdrCommand(adr_id=adr_id, user_id=user_id)))

    uow = uow_factory.unit_of_works[0]
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ADRPublished)
    assert event.adr_id.value == adr_id
    assert not hasattr(event, "user_id")
    assert not hasattr(event, "content")

    assert len(uow.adr_projection.marked_proposed) == 1
    marked_id, marked_at = uow.adr_projection.marked_proposed[0]
    assert marked_id == adr_id
    assert marked_at == event.occurred_at

    assert len(uow.event_store.marked_processed) == 1
    processed_id, processed_at = uow.event_store.marked_processed[0]
    assert processed_at == event.occurred_at
    assert processed_id is not None


def test_publish_adr_raises_not_found_when_adr_missing() -> None:
    handler = PublishAdrCommandHandler(
        FakeUnitOfWorkFactory(),
        FakeAdrRepository(by_id=None),
    )

    with pytest.raises(AdrNotFound):
        asyncio.run(handler.handle(PublishAdrCommand(adr_id=uuid4(), user_id=uuid4())))


@pytest.mark.parametrize(
    "status",
    [
        AdrStatus.DRAFT.value,
        AdrStatus.IN_REVIEW.value,
        AdrStatus.PROPOSED.value,
    ],
)
def test_publish_adr_rejects_non_after_review_status(status: str) -> None:
    user_id = uuid4()
    adr_id = uuid4()
    repository = FakeAdrRepository(
        by_id=_adr_read_model(adr_id=adr_id, user_id=user_id, status=status)
    )
    handler = PublishAdrCommandHandler(FakeUnitOfWorkFactory(), repository)

    with pytest.raises(AdrInvalidPublishStatus, match="after_review"):
        asyncio.run(handler.handle(PublishAdrCommand(adr_id=adr_id, user_id=user_id)))
