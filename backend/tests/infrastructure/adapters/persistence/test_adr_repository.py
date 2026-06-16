"""ADR read repository adapter integration tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from application.ports.adr_repository import AdrReadModel
from infrastructure.adapters.persistence.database_url import (
    normalize_runtime_database_url,
)
from infrastructure.adapters.persistence.projections.adr_projection import (
    SqlAdrProjection,
)
from infrastructure.adapters.persistence.repositories.adr_repository import (
    SqlAdrRepository,
)
from tests.domain.adr.builders import draft_adr


def _adr_read_model(
    *,
    adr_id,
    user_id,
    title: str,
    content: str = "## Context",
    status: str = "draft",
    is_deleted: bool = False,
) -> AdrReadModel:
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    return AdrReadModel(
        id=adr_id,
        user_id=user_id,
        title=title,
        content=content,
        status=status,
        is_deleted=is_deleted,
        created_at=now,
        updated_at=now,
    )


def test_adr_repository_find_by_id_for_owner_filters_deleted_and_other_users(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    owner_id = uuid4()
    other_user_id = uuid4()
    adr_id = uuid4()
    deleted_adr_id = uuid4()
    other_user_adr_id = uuid4()
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)

    async def seed() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.insert(
                        draft_adr(
                            adr_id=adr_id,
                            user_id=owner_id,
                            title="Active ADR",
                            content="content",
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    await projection.insert(
                        draft_adr(
                            adr_id=deleted_adr_id,
                            user_id=owner_id,
                            title="Deleted ADR",
                            content="content",
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    await projection.insert(
                        draft_adr(
                            adr_id=other_user_adr_id,
                            user_id=other_user_id,
                            title="Other user ADR",
                            content="content",
                            created_at=now,
                            updated_at=now,
                        )
                    )
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        text("UPDATE adrs SET is_deleted = true WHERE id = :adr_id"),
                        {"adr_id": deleted_adr_id},
                    )
        finally:
            await engine.dispose()

    asyncio.run(seed())

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repository = SqlAdrRepository(session_factory)
        try:
            found = await repository.find_by_id_for_owner(adr_id, owner_id)
            assert found == _adr_read_model(
                adr_id=adr_id, user_id=owner_id, title="Active ADR", content="content"
            )

            assert (
                await repository.find_by_id_for_owner(deleted_adr_id, owner_id) is None
            )
            assert (
                await repository.find_by_id_for_owner(other_user_adr_id, owner_id)
                is None
            )
            assert await repository.find_by_id_for_owner(adr_id, other_user_id) is None
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_adr_repository_find_by_title_is_case_insensitive_for_owner(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    owner_id = uuid4()
    adr_id = uuid4()
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)

    async def seed() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.insert(
                        draft_adr(
                            adr_id=adr_id,
                            user_id=owner_id,
                            title="Choose Event Store",
                            content="content",
                            created_at=now,
                            updated_at=now,
                        )
                    )
        finally:
            await engine.dispose()

    asyncio.run(seed())

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repository = SqlAdrRepository(session_factory)
        try:
            found = await repository.find_by_title_for_owner(
                "choose event store", owner_id
            )
            assert found is not None
            assert found.id == adr_id
            assert found.title == "Choose Event Store"

            assert (
                await repository.find_by_title_for_owner("missing title", owner_id)
                is None
            )
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_adr_repository_search_by_title_returns_owner_matches_only(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    owner_id = uuid4()
    other_user_id = uuid4()
    matching_id = uuid4()
    other_match_id = uuid4()
    deleted_id = uuid4()
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)

    async def seed() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.insert(
                        draft_adr(
                            adr_id=matching_id,
                            user_id=owner_id,
                            title="Event Store Decision",
                            content="content",
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    await projection.insert(
                        draft_adr(
                            adr_id=other_match_id,
                            user_id=other_user_id,
                            title="Event Store for Other User",
                            content="content",
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    await projection.insert(
                        draft_adr(
                            adr_id=deleted_id,
                            user_id=owner_id,
                            title="Deleted Event Store",
                            content="content",
                            created_at=now,
                            updated_at=now,
                        )
                    )
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        text("UPDATE adrs SET is_deleted = true WHERE id = :adr_id"),
                        {"adr_id": deleted_id},
                    )
        finally:
            await engine.dispose()

    asyncio.run(seed())

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repository = SqlAdrRepository(session_factory)
        try:
            results = await repository.search_by_title(owner_id, "event")
            assert [adr.id for adr in results] == [matching_id]

            assert await repository.search_by_title(owner_id, "nomatch") == []
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())
