"""Rebuild User aggregate state from stored domain events."""

from __future__ import annotations

from collections.abc import Sequence

from domain.events import DomainEvent
from domain.user.aggregate import User


def rehydrate_user(events: Sequence[DomainEvent]) -> User | None:
    """Fold an ordered event stream into a ``User`` via ``User.restore``."""
    return User.restore(events)
