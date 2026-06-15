from contextlib import AbstractAsyncContextManager
from typing import Protocol

from application.ports.event_store import EventStore
from application.ports.user_projection import UserProjection


class UnitOfWork(Protocol):
    event_store: EventStore
    user_projection: UserProjection

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def begin(self) -> AbstractAsyncContextManager[UnitOfWork]: ...
