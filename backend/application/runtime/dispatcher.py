"""Event handler registry and dispatch loop."""

import time
from collections.abc import Awaitable, Callable

from application.logging import get_logger
from application.ports.event_store import StoredEvent
from domain.events import DomainEvent

EventHandler = Callable[[StoredEvent], Awaitable[None]]


class EventDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, EventHandler] = {}
        self._logger = get_logger(__name__)

    def register(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type.__name__] = handler

    async def dispatch(self, stored_event: StoredEvent) -> None:
        event_type_name = type(stored_event.event).__name__
        stored_event_id = str(stored_event.id)
        handler = self._handlers.get(event_type_name)
        if handler is None:
            self._logger.warning(
                "dispatcher.no_handler",
                event_type=event_type_name,
                stored_event_id=stored_event_id,
            )
            return

        self._logger.info(
            "dispatcher.dispatch.started",
            event_type=event_type_name,
            stored_event_id=stored_event_id,
        )
        start = time.perf_counter()
        try:
            await handler(stored_event)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000)
            self._logger.error(
                "dispatcher.dispatch.failed",
                event_type=event_type_name,
                stored_event_id=stored_event_id,
                error=str(exc),
                duration_ms=duration_ms,
                exc_info=True,
            )
            raise

        duration_ms = round((time.perf_counter() - start) * 1000)
        self._logger.info(
            "dispatcher.dispatch.completed",
            event_type=event_type_name,
            stored_event_id=stored_event_id,
            duration_ms=duration_ms,
        )
