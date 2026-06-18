from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from application.ports.adr_projection import AdrProjection
from application.ports.event_store import EventStore
from application.ports.user_projection import UserProjection


class UnitOfWork(Protocol):
    event_store: EventStore
    user_projection: UserProjection
    adr_projection: AdrProjection

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def lock_aggregate(self, aggregate_id: UUID) -> None: ...


class UnitOfWorkFactory(Protocol):
    def begin(self) -> AbstractAsyncContextManager[UnitOfWork]: ...
