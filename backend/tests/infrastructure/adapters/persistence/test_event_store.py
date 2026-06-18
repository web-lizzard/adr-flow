"""Event store replay integration tests."""

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from domain.adr.events import ADRPublished, ADRSubmittedForReview
from domain.adr.value_objects import AdrContent, AdrId
from domain.user.events import UserRegistered
from domain.user.value_objects import EmailAddress, PasswordHash, UserId
from infrastructure.adapters.persistence.database_url import (
    normalize_runtime_database_url,
)
from infrastructure.adapters.persistence.event_store import SqlEventStore


def test_event_store_loads_unprocessed_events_in_order_and_marks_processed(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    adr_id = uuid4()
    user_id = uuid4()
    first_at = datetime(2026, 6, 17, 10, 0, tzinfo=UTC)
    second_at = datetime(2026, 6, 17, 11, 0, tzinfo=UTC)
    processed_at = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    store = SqlEventStore(session)
                    await store.append(
                        [
                            ADRSubmittedForReview(
                                adr_id=AdrId(adr_id),
                                user_id=UserId(user_id),
                                content=AdrContent("## Context\n\nTBD"),
                                occurred_at=first_at,
                            ),
                            ADRSubmittedForReview(
                                adr_id=AdrId(adr_id),
                                user_id=UserId(user_id),
                                content=AdrContent("## Context\n\nUpdated"),
                                occurred_at=second_at,
                            ),
                        ],
                        aggregate_id=adr_id,
                        aggregate_type="ADR",
                    )

            async with session_factory() as session:
                store = SqlEventStore(session)
                unprocessed = await store.load_unprocessed(limit=10)
                assert len(unprocessed) == 2
                assert unprocessed[0].event.occurred_at == first_at
                assert unprocessed[1].event.occurred_at == second_at
                assert isinstance(unprocessed[0].event, ADRSubmittedForReview)
                assert unprocessed[0].event.content.value == "## Context\n\nTBD"

            async with session_factory() as session:
                async with session.begin():
                    store = SqlEventStore(session)
                    unprocessed = await store.load_unprocessed(limit=1)
                    await store.mark_processed(
                        unprocessed[0].id,
                        processed_at=processed_at,
                    )

            async with session_factory() as session:
                store = SqlEventStore(session)
                remaining = await store.load_unprocessed(limit=10)
                assert len(remaining) == 1
                assert remaining[0].event.occurred_at == second_at
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_event_store_skips_sync_projection_events_for_async_replay(
    postgres_url: str, db_engine
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM events"))

    user_id = uuid4()
    occurred_at = datetime(2026, 6, 17, 10, 0, tzinfo=UTC)

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    store = SqlEventStore(session)
                    await store.append(
                        [
                            UserRegistered(
                                user_id=UserId(user_id),
                                email=EmailAddress("alice@example.com"),
                                password_hash=PasswordHash("hashed"),
                                occurred_at=occurred_at,
                            )
                        ],
                        aggregate_id=user_id,
                        aggregate_type="User",
                    )

            async with session_factory() as session:
                store = SqlEventStore(session)
                unprocessed = await store.load_unprocessed(limit=10)
                assert unprocessed == []
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_event_store_skips_adr_published_for_async_replay(
    postgres_url: str, db_engine
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM events"))

    adr_id = uuid4()
    occurred_at = datetime(2026, 6, 17, 10, 0, tzinfo=UTC)

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    store = SqlEventStore(session)
                    await store.append(
                        [
                            ADRPublished(
                                adr_id=AdrId(adr_id),
                                occurred_at=occurred_at,
                            )
                        ],
                        aggregate_id=adr_id,
                        aggregate_type="adr",
                    )

            async with session_factory() as session:
                store = SqlEventStore(session)
                unprocessed = await store.load_unprocessed(limit=10)
                assert unprocessed == []
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_event_store_skips_unknown_events_for_async_replay(
    postgres_url: str, db_engine
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM events"))

    adr_id = uuid4()
    user_id = uuid4()
    unknown_at = datetime(2026, 6, 17, 9, 0, tzinfo=UTC)
    review_at = datetime(2026, 6, 17, 10, 0, tzinfo=UTC)

    with db_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO events (
                    id, aggregate_type, aggregate_id, event_type, payload,
                    occurred_at, processed_at
                ) VALUES (
                    :id, 'adr', :aggregate_id, 'FutureEvent', '{}',
                    :occurred_at, NULL
                )
                """
            ),
            {
                "id": uuid4(),
                "aggregate_id": adr_id,
                "occurred_at": unknown_at,
            },
        )

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    store = SqlEventStore(session)
                    await store.append(
                        [
                            ADRSubmittedForReview(
                                adr_id=AdrId(adr_id),
                                user_id=UserId(user_id),
                                content=AdrContent("## Context\n\nTBD"),
                                occurred_at=review_at,
                            )
                        ],
                        aggregate_id=adr_id,
                        aggregate_type="ADR",
                    )

            async with session_factory() as session:
                store = SqlEventStore(session)
                unprocessed = await store.load_unprocessed(limit=10)
                assert len(unprocessed) == 1
                assert isinstance(unprocessed[0].event, ADRSubmittedForReview)
                assert unprocessed[0].event.occurred_at == review_at
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())


def test_mark_sync_projection_events_skips_legacy_content_updated_payload(
    postgres_url: str, db_engine
) -> None:
    """Legacy ADRContentUpdated rows omit title; bulk mark avoids deserialization."""
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM events"))

    adr_id = uuid4()
    occurred_at = datetime(2026, 6, 16, 18, 50, 16, tzinfo=UTC)
    legacy_payload = {
        "adr_id": {"value": str(adr_id)},
        "content": {"value": "## Context\n\nOld"},
        "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
    }

    with db_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO events (
                    id, aggregate_type, aggregate_id, event_type, payload,
                    occurred_at, processed_at
                ) VALUES (
                    :id, 'adr', :aggregate_id, 'ADRContentUpdated', :payload,
                    :occurred_at, NULL
                )
                """
            ),
            {
                "id": uuid4(),
                "aggregate_id": adr_id,
                "payload": json.dumps(legacy_payload),
                "occurred_at": occurred_at,
            },
        )

    processed_at = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    store = SqlEventStore(session)
                    await store.mark_sync_projection_events_processed(
                        processed_at=processed_at
                    )

            async with session_factory() as session:
                store = SqlEventStore(session)
                unprocessed = await store.load_unprocessed(limit=10)
                assert unprocessed == []
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())
