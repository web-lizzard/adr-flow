"""ListAdrs query handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from application.ports.adr_repository import AdrReadModel
from application.queries.list_adrs import ListAdrsQuery, ListAdrsQueryHandler


def _adr_read_model(*, adr_id, user_id, title: str) -> AdrReadModel:
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
    def __init__(self, *, results: list[AdrReadModel] | None = None) -> None:
        self._results = results or []
        self.list_calls: list = []

    async def find_by_id_for_owner(self, adr_id, user_id):
        return None

    async def find_by_title_for_owner(self, title: str, user_id):
        return None

    async def search_by_title(self, user_id, query: str):
        return []

    async def list_for_owner(self, user_id, *, limit: int = 50, offset: int = 0):
        self.list_calls.append((user_id, limit, offset))
        return self._results


def test_list_adrs_returns_repository_results_for_user() -> None:
    user_id = uuid4()
    adrs = [
        _adr_read_model(adr_id=uuid4(), user_id=user_id, title="First ADR"),
        _adr_read_model(adr_id=uuid4(), user_id=user_id, title="Second ADR"),
    ]
    repository = FakeAdrRepository(results=adrs)
    handler = ListAdrsQueryHandler(repository)

    result = asyncio.run(handler.handle(ListAdrsQuery(user_id=user_id)))

    assert result == adrs
    assert repository.list_calls == [(user_id, 50, 0)]


def test_list_adrs_returns_empty_list_for_user_with_no_adrs() -> None:
    user_id = uuid4()
    repository = FakeAdrRepository(results=[])
    handler = ListAdrsQueryHandler(repository)

    result = asyncio.run(handler.handle(ListAdrsQuery(user_id=user_id)))

    assert result == []


def test_list_adrs_forwards_pagination_values() -> None:
    user_id = uuid4()
    repository = FakeAdrRepository(results=[])
    handler = ListAdrsQueryHandler(repository)

    asyncio.run(handler.handle(ListAdrsQuery(user_id=user_id, limit=10, offset=20)))

    assert repository.list_calls == [(user_id, 10, 20)]
