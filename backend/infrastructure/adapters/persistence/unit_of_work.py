"""SQLAlchemy unit-of-work adapter for atomic write-side transactions."""

import struct
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import IntegrityError

from application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from domain.errors import AdrTitleAlreadyExists, EmailAlreadyTaken
from infrastructure.adapters.persistence.event_store import SqlEventStore
from infrastructure.adapters.persistence.projections.adr_projection import (
    SqlAdrProjection,
)
from infrastructure.adapters.persistence.projections.user_projection import (
    SqlUserProjection,
)


class SqlUnitOfWork(UnitOfWork):
    def __init__(
        self,
        session: AsyncSession,
        event_store: SqlEventStore,
        user_projection: SqlUserProjection,
        adr_projection: SqlAdrProjection,
    ) -> None:
        self.event_store = event_store
        self.user_projection = user_projection
        self.adr_projection = adr_projection
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def lock_aggregate(self, aggregate_id: UUID) -> None:
        # Signed int32 pair from the first 8 bytes of the aggregate UUID.
        hi, lo = struct.unpack("!ii", aggregate_id.bytes[:8])
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:hi, :lo)"),
            {"hi": hi, "lo": lo},
        )


class SqlUnitOfWorkFactory(UnitOfWorkFactory):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[SqlUnitOfWork]:
        async with self._session_factory() as session:
            try:
                async with session.begin():
                    event_store = SqlEventStore(session)
                    user_projection = SqlUserProjection(session)
                    adr_projection = SqlAdrProjection(session)
                    yield SqlUnitOfWork(
                        session=session,
                        event_store=event_store,
                        user_projection=user_projection,
                        adr_projection=adr_projection,
                    )
            except IntegrityError as exc:
                if _is_users_email_unique_violation(exc):
                    raise EmailAlreadyTaken() from exc
                if _is_adrs_active_user_title_unique_violation(exc):
                    raise AdrTitleAlreadyExists() from exc
                raise


def _is_users_email_unique_violation(exc: IntegrityError) -> bool:
    if _constraint_name(exc.orig) == "users_email_key":
        return True
    return "users_email_key" in str(exc.orig) or "users_email_key" in str(exc)


def _is_adrs_active_user_title_unique_violation(exc: IntegrityError) -> bool:
    constraint = "uq_adrs_active_user_title_ci"
    if _constraint_name(exc.orig) == constraint:
        return True
    return constraint in str(exc.orig) or constraint in str(exc)


def _constraint_name(error: object) -> str | None:
    current = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        constraint_name = getattr(current, "constraint_name", None)
        if isinstance(constraint_name, str):
            return constraint_name
        current = getattr(current, "__cause__", None) or getattr(
            current, "__context__", None
        )
    return None
