"""ADR projection review lifecycle integration tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from application.review_metadata import ReviewErrorMetadata
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from infrastructure.adapters.persistence.database_url import (
    normalize_runtime_database_url,
)
from infrastructure.adapters.persistence.models import Adr
from infrastructure.adapters.persistence.projections.adr_projection import (
    SqlAdrProjection,
)
from tests.domain.adr.builders import draft_adr


def test_adr_projection_review_lifecycle(
    postgres_url: str,
    db_engine,
) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))

    adr_id = uuid4()
    user_id = uuid4()
    created_at = datetime(2026, 6, 17, 10, 0, tzinfo=UTC)
    in_review_at = datetime(2026, 6, 17, 11, 0, tzinfo=UTC)
    reviewed_at = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)
    failed_at = datetime(2026, 6, 17, 13, 0, tzinfo=UTC)
    source_event_id = uuid4()

    review_result = ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Consequences section",
                location="## Consequences",
                suggestion="Describe trade-offs.",
            ),
        ),
        reviewed_at=reviewed_at,
    )

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
                            title="Review lifecycle",
                            content="## Context\n\nTBD",
                            created_at=created_at,
                            updated_at=created_at,
                        )
                    )

            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.mark_in_review(adr_id, updated_at=in_review_at)

            async with session_factory() as session:
                row = (
                    await session.execute(select(Adr).where(Adr.id == adr_id))
                ).scalar_one()
                assert row.status == "in_review"
                assert row.review_annotations is None
                assert row.review_error is None
                assert row.updated_at == in_review_at

            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.apply_review_result(
                        adr_id,
                        review_result=review_result,
                        updated_at=reviewed_at,
                    )

            async with session_factory() as session:
                row = (
                    await session.execute(select(Adr).where(Adr.id == adr_id))
                ).scalar_one()
                assert row.status == "after_review"
                assert row.reviewed_at == reviewed_at
                assert row.review_error is None
                assert row.review_annotations is not None
                annotations_before_publish = row.review_annotations

            proposed_at = datetime(2026, 6, 17, 13, 0, tzinfo=UTC)
            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.mark_proposed(adr_id, updated_at=proposed_at)

            async with session_factory() as session:
                row = (
                    await session.execute(select(Adr).where(Adr.id == adr_id))
                ).scalar_one()
                assert row.status == "proposed"
                assert row.reviewed_at == reviewed_at
                assert row.review_annotations == annotations_before_publish
                assert row.updated_at == proposed_at

            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.mark_in_review(adr_id, updated_at=in_review_at)

            async with session_factory() as session:
                async with session.begin():
                    projection = SqlAdrProjection(session)
                    await projection.record_review_failure(
                        adr_id,
                        review_error=ReviewErrorMetadata(
                            source_event_id=source_event_id,
                            code="validation_failed",
                            message="Invalid review output",
                            failed_at=failed_at,
                        ),
                        updated_at=failed_at,
                    )

            async with session_factory() as session:
                row = (
                    await session.execute(select(Adr).where(Adr.id == adr_id))
                ).scalar_one()
                assert row.status == "in_review"
                assert row.review_error == {
                    "source_event_id": str(source_event_id),
                    "code": "validation_failed",
                    "message": "Invalid review output",
                    "failed_at": failed_at.isoformat(),
                }
        finally:
            await engine.dispose()

    asyncio.run(run_scenario())
