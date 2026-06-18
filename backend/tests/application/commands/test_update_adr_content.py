"""UpdateAdrContent command handler tests."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from application.commands.update_adr_content import (
    UpdateAdrContentCommand,
    UpdateAdrContentCommandHandler,
)
from application.ports.adr_repository import AdrReadModel
from application.ports.event_store import StoredEvent
from domain.adr import ADRContentUpdated, AdrStatus
from domain.errors import AdrEditWhileInReview, AdrNotFound, AdrTitleAlreadyExists


class FakeEventStore:
    def __init__(self) -> None:
        self.appended: list[tuple[list, UUID, str]] = []
        self.marked_processed: list[tuple[UUID, datetime]] = []

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

    async def mark_processed(self, event_id: UUID, *, processed_at: datetime) -> None:
        self.marked_processed.append((event_id, processed_at))


class FakeAdrProjection:
    def __init__(self) -> None:
        self.updated: list = []

    async def insert(self, adr) -> None:
        return None

    async def update_content(self, adr) -> None:
        self.updated.append(adr)

    async def mark_in_review(self, adr_id: UUID, *, updated_at: datetime) -> None:
        return None

    async def mark_proposed(self, adr_id: UUID, *, updated_at: datetime) -> bool:
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
    def __init__(
        self,
        *,
        by_id: AdrReadModel | None = None,
        by_title: AdrReadModel | None = None,
    ) -> None:
        self._by_id = by_id
        self._by_title = by_title

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
        if self._by_title is None:
            return None
        if self._by_title.user_id != user_id:
            return None
        if self._by_title.title.lower() != title.lower():
            return None
        return self._by_title

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
    title: str = "My ADR",
    content: str = "## Context",
    status: str = "draft",
) -> AdrReadModel:
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    return AdrReadModel(
        id=adr_id,
        user_id=user_id,
        title=title,
        content=content,
        status=status,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )


def test_update_adr_content_emits_event_and_updates_projection() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    repository = FakeAdrRepository(
        by_id=_adr_read_model(adr_id=adr_id, user_id=user_id, content="old")
    )
    uow_factory = FakeUnitOfWorkFactory()
    handler = UpdateAdrContentCommandHandler(uow_factory, repository)

    asyncio.run(
        handler.handle(
            UpdateAdrContentCommand(
                adr_id=adr_id,
                user_id=user_id,
                title=None,
                content="## Context\n\nUpdated",
            )
        )
    )

    uow = uow_factory.unit_of_works[0]
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    event = events[0]
    assert isinstance(event, ADRContentUpdated)
    assert event.content.value == "## Context\n\nUpdated"
    assert event.title is None

    updated = uow.adr_projection.updated[0]
    assert updated.content.value == "## Context\n\nUpdated"
    assert updated.title.value == "My ADR"


def test_update_adr_content_includes_title_on_event_when_title_changes() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    repository = FakeAdrRepository(
        by_id=_adr_read_model(adr_id=adr_id, user_id=user_id, title="Original")
    )
    uow_factory = FakeUnitOfWorkFactory()
    handler = UpdateAdrContentCommandHandler(uow_factory, repository)

    asyncio.run(
        handler.handle(
            UpdateAdrContentCommand(
                adr_id=adr_id,
                user_id=user_id,
                title="Renamed",
                content=None,
            )
        )
    )

    event = uow_factory.unit_of_works[0].event_store.appended[0][0][0]
    assert isinstance(event, ADRContentUpdated)
    assert event.title is not None
    assert event.title.value == "Renamed"
    assert event.content.value == "## Context"


def test_update_adr_content_checks_title_uniqueness_when_title_changes() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    other_id = uuid4()
    repository = FakeAdrRepository(
        by_id=_adr_read_model(adr_id=adr_id, user_id=user_id, title="Original"),
        by_title=_adr_read_model(adr_id=other_id, user_id=user_id, title="Taken"),
    )
    handler = UpdateAdrContentCommandHandler(FakeUnitOfWorkFactory(), repository)

    with pytest.raises(AdrTitleAlreadyExists):
        asyncio.run(
            handler.handle(
                UpdateAdrContentCommand(
                    adr_id=adr_id,
                    user_id=user_id,
                    title="Taken",
                    content=None,
                )
            )
        )


def test_update_adr_content_raises_not_found_when_adr_missing() -> None:
    handler = UpdateAdrContentCommandHandler(
        FakeUnitOfWorkFactory(),
        FakeAdrRepository(by_id=None),
    )

    with pytest.raises(AdrNotFound):
        asyncio.run(
            handler.handle(
                UpdateAdrContentCommand(
                    adr_id=uuid4(),
                    user_id=uuid4(),
                    title=None,
                    content="new",
                )
            )
        )


def test_update_adr_content_rejects_in_review_status() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    repository = FakeAdrRepository(
        by_id=_adr_read_model(
            adr_id=adr_id,
            user_id=user_id,
            status=AdrStatus.IN_REVIEW.value,
        )
    )
    handler = UpdateAdrContentCommandHandler(FakeUnitOfWorkFactory(), repository)

    with pytest.raises(AdrEditWhileInReview):
        asyncio.run(
            handler.handle(
                UpdateAdrContentCommand(
                    adr_id=adr_id,
                    user_id=user_id,
                    title=None,
                    content="blocked",
                )
            )
        )
