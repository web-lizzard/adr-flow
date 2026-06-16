"""GetAdr query handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.queries.get_adr import GetAdrQuery, GetAdrQueryHandler
from application.ports.adr_repository import AdrReadModel
from domain.errors import AdrNotFound


def _adr_read_model(*, adr_id, user_id, title: str = "My ADR") -> AdrReadModel:
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    return AdrReadModel(
        id=adr_id,
        user_id=user_id,
        title=title,
        content="## Context",
        status="draft",
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )


class FakeAdrRepository:
    def __init__(self, *, by_id: AdrReadModel | None = None) -> None:
        self._by_id = by_id
        self.lookups: list[tuple] = []

    async def find_by_id_for_owner(self, adr_id, user_id):
        self.lookups.append((adr_id, user_id))
        return self._by_id

    async def find_by_title_for_owner(self, title: str, user_id):
        return None

    async def search_by_title(self, user_id, query: str):
        return []

    async def list_for_owner(
        self,
        user_id,
        *,
        limit: int = 50,
        offset: int = 0,
    ):
        return []


def test_get_adr_returns_read_model_for_owner() -> None:
    user_id = uuid4()
    adr_id = uuid4()
    read_model = _adr_read_model(adr_id=adr_id, user_id=user_id)
    repository = FakeAdrRepository(by_id=read_model)
    handler = GetAdrQueryHandler(repository)

    result = asyncio.run(handler.handle(GetAdrQuery(adr_id=adr_id, user_id=user_id)))

    assert result == read_model
    assert repository.lookups == [(adr_id, user_id)]


def test_get_adr_raises_not_found_when_missing_or_not_owned() -> None:
    handler = GetAdrQueryHandler(FakeAdrRepository(by_id=None))

    with pytest.raises(AdrNotFound):
        asyncio.run(handler.handle(GetAdrQuery(adr_id=uuid4(), user_id=uuid4())))
