"""Lifespan-managed async event dispatch loop."""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress

from application.logging import get_logger
from application.ports.event_store import StoredEvent

DispatchFn = Callable[[StoredEvent], Awaitable[None]]
DrainFn = Callable[[], Awaitable[int]]


class TaskGroupEventBus:
    def __init__(self) -> None:
        self._dispatch: DispatchFn | None = None
        self._worker_task: asyncio.Task[None] | None = None
        self._wake_event: asyncio.Event | None = None
        self._stop_requested = False
        self._logger = get_logger(__name__)

    def set_dispatch(self, dispatch_fn: DispatchFn) -> None:
        self._dispatch = dispatch_fn

    def start_worker(
        self,
        drain_fn: DrainFn,
        *,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        if self._worker_task is not None:
            self._logger.debug("event_bus.worker_already_running")
            return
        self._stop_requested = False
        self._wake_event = asyncio.Event()
        self._worker_task = asyncio.create_task(
            self._run_worker(drain_fn, poll_interval_seconds)
        )
        self._logger.info(
            "event_bus.worker_started",
            poll_interval_seconds=poll_interval_seconds,
        )

    async def dispatch_now(self, stored_event: StoredEvent) -> None:
        if self._dispatch is None:
            self._logger.warning("event_bus.dispatch_not_configured")
            return
        self._logger.info(
            "event_bus.dispatch_inline",
            stored_event_id=str(stored_event.id),
            event_type=type(stored_event.event).__name__,
        )
        await self._dispatch(stored_event)

    async def stop_worker(self) -> None:
        if self._worker_task is None:
            return
        self._logger.info("event_bus.worker_stopping")
        self._stop_requested = True
        if self._wake_event is not None:
            self._wake_event.set()
        with suppress(asyncio.CancelledError):
            await self._worker_task
        self._worker_task = None
        self._wake_event = None
        self._logger.info("event_bus.worker_stopped")

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
                self._logger.error("event_bus.drain_failed", exc_info=True)

            self._logger.debug("event_bus.drain_cycle", drained_count=drained_count)

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
