"""CreateAdr command handler tests."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from application.commands.create_adr import CreateAdrCommand, CreateAdrCommandHandler
from application.ports.adr_repository import AdrReadModel
from domain.adr import ADR_STARTER_TEMPLATE, ADRCreated, AdrStatus
from domain.errors import AdrTitleAlreadyExists


class FakeEventStore:
    def __init__(self) -> None:
        self.appended: list[tuple[list, UUID, str]] = []

    async def append(
        self, events: list, aggregate_id: UUID, aggregate_type: str
    ) -> None:
        self.appended.append((events, aggregate_id, aggregate_type))


class FakeAdrProjection:
    def __init__(self) -> None:
        self.inserted: list = []

    async def insert(self, adr) -> None:
        self.inserted.append(adr)


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
    def __init__(self, *, by_title: AdrReadModel | None = None) -> None:
        self._by_title = by_title
        self.title_lookups: list[tuple[str, UUID]] = []

    async def find_by_id_for_owner(
        self, adr_id: UUID, user_id: UUID
    ) -> AdrReadModel | None:
        return None

    async def find_by_title_for_owner(
        self, title: str, user_id: UUID
    ) -> AdrReadModel | None:
        self.title_lookups.append((title, user_id))
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


def _adr_read_model(*, adr_id: UUID, user_id: UUID, title: str) -> AdrReadModel:
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    return AdrReadModel(
        id=adr_id,
        user_id=user_id,
        title=title,
        content=ADR_STARTER_TEMPLATE,
        status=AdrStatus.DRAFT.value,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )


def test_create_adr_emits_event_and_inserts_projection_with_starter_template() -> None:
    user_id = uuid4()
    uow_factory = FakeUnitOfWorkFactory()
    repository = FakeAdrRepository()
    handler = CreateAdrCommandHandler(uow_factory, repository)

    adr_id = asyncio.run(
        handler.handle(CreateAdrCommand(user_id=user_id, title="My ADR"))
    )

    assert isinstance(adr_id, UUID)
    uow = uow_factory.unit_of_works[0]
    assert len(uow.event_store.appended) == 1
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ADRCreated)
    assert event.title.value == "My ADR"
    assert event.content.value == ADR_STARTER_TEMPLATE

    assert len(uow.adr_projection.inserted) == 1
    inserted = uow.adr_projection.inserted[0]
    assert inserted.adr_id.value == adr_id
    assert inserted.user_id.value == user_id
    assert inserted.title.value == "My ADR"
    assert inserted.content.value == ADR_STARTER_TEMPLATE
    assert inserted.status == AdrStatus.DRAFT


def test_create_adr_raises_when_title_already_exists_for_user() -> None:
    user_id = uuid4()
    existing_id = uuid4()
    repository = FakeAdrRepository(
        by_title=_adr_read_model(adr_id=existing_id, user_id=user_id, title="Taken")
    )
    handler = CreateAdrCommandHandler(FakeUnitOfWorkFactory(), repository)

    with pytest.raises(AdrTitleAlreadyExists):
        asyncio.run(handler.handle(CreateAdrCommand(user_id=user_id, title="Taken")))
