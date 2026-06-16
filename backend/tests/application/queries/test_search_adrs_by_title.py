"""SearchAdrsByTitle query handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from application.queries.search_adrs_by_title import (
    SearchAdrsByTitleQuery,
    SearchAdrsByTitleQueryHandler,
)
from application.ports.adr_repository import AdrReadModel


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
        self.searches: list[tuple] = []

    async def find_by_id_for_owner(self, adr_id, user_id):
        return None

    async def find_by_title_for_owner(self, title: str, user_id):
        return None

    async def search_by_title(self, user_id, query: str):
        self.searches.append((user_id, query))
        return self._results

    async def list_for_owner(
        self,
        user_id,
        *,
        limit: int = 50,
        offset: int = 0,
    ):
        return []


def test_search_adrs_by_title_returns_repository_matches_for_user() -> None:
    user_id = uuid4()
    matches = [
        _adr_read_model(adr_id=uuid4(), user_id=user_id, title="Auth ADR"),
        _adr_read_model(adr_id=uuid4(), user_id=user_id, title="Auth patterns"),
    ]
    repository = FakeAdrRepository(results=matches)
    handler = SearchAdrsByTitleQueryHandler(repository)

    result = asyncio.run(
        handler.handle(SearchAdrsByTitleQuery(user_id=user_id, query="auth"))
    )

    assert result == matches
    assert repository.searches == [(user_id, "auth")]


def test_search_adrs_by_title_returns_empty_list_when_no_matches() -> None:
    user_id = uuid4()
    repository = FakeAdrRepository(results=[])
    handler = SearchAdrsByTitleQueryHandler(repository)

    result = asyncio.run(
        handler.handle(SearchAdrsByTitleQuery(user_id=user_id, query="missing"))
    )

    assert result == []
