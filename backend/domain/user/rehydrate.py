"""Rebuild User aggregate state from stored domain events."""

from __future__ import annotations

from collections.abc import Sequence

from domain.events import DomainEvent
from domain.user.aggregate import User
from domain.user.events import UserRegistered


def rehydrate_user(events: Sequence[DomainEvent]) -> User | None:
    """Fold an ordered event stream into a ``User``.

    Maps ``UserRegistered`` to value objects and ``User.create``. This module
    is the event-type dispatch boundary; ``aggregate.py`` does not import events.

    Returns ``None`` for an empty stream. Raises ``ValueError`` for unknown
    event types.
    """
    if not events:
        return None

    user: User | None = None
    for event in events:
        match event:
            case UserRegistered():
                user = User.create(
                    user_id=event.user_id,
                    email=event.email,
                    password_hash=event.password_hash,
                    created_at=event.occurred_at,
                )
            case _:
                msg = f"Unknown event type: {type(event).__name__}"
                raise ValueError(msg)
    return user
