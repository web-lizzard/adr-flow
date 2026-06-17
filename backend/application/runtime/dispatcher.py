"""Event handler registry and dispatch loop."""

import logging
from collections.abc import Awaitable, Callable

from application.ports.event_store import StoredEvent
from domain.events import DomainEvent

EventHandler = Callable[[StoredEvent], Awaitable[None]]


class EventDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, EventHandler] = {}
        self._logger = logging.getLogger(__name__)

    def register(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type.__name__] = handler

    async def dispatch(self, stored_event: StoredEvent) -> None:
        event_type_name = type(stored_event.event).__name__
        handler = self._handlers.get(event_type_name)
        if handler is None:
            self._logger.warning(
                "No handler registered for event type %s", event_type_name
            )
            return
        await handler(stored_event)
