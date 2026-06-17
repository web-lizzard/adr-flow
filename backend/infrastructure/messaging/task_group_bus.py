"""Lifespan-managed async event dispatch loop."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress

from application.ports.event_store import StoredEvent

DispatchFn = Callable[[StoredEvent], Awaitable[None]]
DrainFn = Callable[[], Awaitable[int]]


class TaskGroupEventBus:
    def __init__(self) -> None:
        self._dispatch: DispatchFn | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._wake_event: asyncio.Event | None = None
        self._stop_requested = False
        self._logger = logging.getLogger(__name__)

    def set_dispatch(self, dispatch_fn: DispatchFn) -> None:
        self._dispatch = dispatch_fn

    def start_worker(
        self,
        drain_fn: DrainFn,
        *,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        if self._worker_task is not None:
            return
        self._stop_requested = False
        self._wake_event = asyncio.Event()
        self._worker_task = asyncio.create_task(
            self._run_worker(drain_fn, poll_interval_seconds)
        )

    async def dispatch_now(self, stored_event: StoredEvent) -> None:
        if self._dispatch is None:
            return
        await self._dispatch(stored_event)

    async def stop_worker(self) -> None:
        if self._worker_task is None:
            return
        self._stop_requested = True
        if self._wake_event is not None:
            self._wake_event.set()
        with suppress(asyncio.CancelledError):
            await self._worker_task
        self._worker_task = None
        self._wake_event = None

    async def _run_worker(
        self,
        drain_fn: DrainFn,
        poll_interval_seconds: float,
    ) -> None:
        while not self._stop_requested:
            try:
                drained_count = await drain_fn()
            except Exception:
                drained_count = 0
                self._logger.exception("Event worker drain failed")

            if drained_count > 0:
                continue

            if self._wake_event is None:
                return
            try:
                await asyncio.wait_for(
                    self._wake_event.wait(), timeout=poll_interval_seconds
                )
            except TimeoutError:
                pass
            self._wake_event.clear()
