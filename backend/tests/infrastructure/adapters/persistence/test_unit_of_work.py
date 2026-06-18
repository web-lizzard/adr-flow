"""Unit-of-work adapter integration tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from domain.errors import AdrTitleAlreadyExists, EmailAlreadyTaken
from infrastructure.adapters.persistence.database_url import (
    normalize_runtime_database_url,
)
from infrastructure.adapters.persistence.unit_of_work import SqlUnitOfWorkFactory
from tests.domain.adr.builders import draft_adr


def test_unit_of_work_exposes_adr_projection(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    adr_id = uuid4()
    user_id = uuid4()
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        uow_factory = SqlUnitOfWorkFactory(session_factory)
        try:
            async with uow_factory.begin() as uow:
                await uow.adr_projection.insert(
                    draft_adr(
                        adr_id=adr_id,
                        user_id=user_id,
                        title="UoW ADR",
                        content="## Context",
                        created_at=now,
                        updated_at=now,
                    )
                )
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_unit_of_work_translates_duplicate_user_email(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        uow_factory = SqlUnitOfWorkFactory(session_factory)
        try:
            async with uow_factory.begin() as uow:
                await uow.user_projection.insert(
                    user_id=uuid4(),
                    email="duplicate@example.com",
                    password_hash="hash",
                    created_at=datetime.now(UTC),
                )

            with pytest.raises(EmailAlreadyTaken):
                async with uow_factory.begin() as uow:
                    await uow.user_projection.insert(
                        user_id=uuid4(),
                        email="duplicate@example.com",
                        password_hash="hash",
                        created_at=datetime.now(UTC),
                    )
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_lock_aggregate_acquires_and_commits_cleanly(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    aggregate_id = uuid4()

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        uow_factory = SqlUnitOfWorkFactory(session_factory)
        try:
            async with uow_factory.begin() as uow:
                await uow.lock_aggregate(aggregate_id)
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_unit_of_work_translates_duplicate_active_adr_title(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    user_id = uuid4()
    now = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        uow_factory = SqlUnitOfWorkFactory(session_factory)
        try:
            async with uow_factory.begin() as uow:
                await uow.adr_projection.insert(
                    draft_adr(
                        adr_id=uuid4(),
                        user_id=user_id,
                        title="Duplicate ADR",
                        content="## Context",
                        created_at=now,
                        updated_at=now,
                    )
                )

            with pytest.raises(AdrTitleAlreadyExists):
                async with uow_factory.begin() as uow:
                    await uow.adr_projection.insert(
                        draft_adr(
                            adr_id=uuid4(),
                            user_id=user_id,
                            title="duplicate adr",
                            content="## Context",
                            created_at=now,
                            updated_at=now,
                        )
                    )
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())
