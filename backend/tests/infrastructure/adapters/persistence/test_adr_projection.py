"""ADR projection adapter integration tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from infrastructure.adapters.persistence.database_url import (
    normalize_runtime_database_url,
)
from infrastructure.adapters.persistence.models import Adr
from infrastructure.adapters.persistence.projections.adr_projection import (
    SqlAdrProjection,
)
from tests.domain.adr.builders import draft_adr


def test_adr_projection_inserts_and_updates_content(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    adr_id = uuid4()
    user_id = uuid4()
    created_at = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    updated_at = datetime(2026, 6, 16, 11, 0, tzinfo=UTC)

    async def run_scenario() -> None:
        engine = create_async_engine(normalize_runtime_database_url(postgres_url))
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.insert(
                        draft_adr(
                            adr_id=adr_id,
                            user_id=user_id,
                            title="Choose event store",
                            content="## Context\n\nTBD",
                            created_at=created_at,
                            updated_at=created_at,
                        )
                    )

            async with session_factory() as session:
                result = await session.execute(select(Adr).where(Adr.id == adr_id))
                row = result.scalar_one()
                assert row.user_id == user_id
                assert row.title == "Choose event store"
                assert row.content == "## Context\n\nTBD"
                assert row.status == "draft"
                assert row.is_deleted is False

            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.update_content(
                        draft_adr(
                            adr_id=adr_id,
                            user_id=user_id,
                            title="Updated title",
                            content="## Context\n\nUpdated",
                            created_at=created_at,
                            updated_at=updated_at,
                        )
                    )

            async with session_factory() as session:
                result = await session.execute(select(Adr).where(Adr.id == adr_id))
                row = result.scalar_one()
                assert row.title == "Updated title"
                assert row.content == "## Context\n\nUpdated"
                assert row.updated_at == updated_at
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())
