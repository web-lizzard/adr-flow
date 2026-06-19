"""Rebuild ADR aggregate state from stored domain events."""

from __future__ import annotations

from collections.abc import Sequence

from domain.adr.aggregate import ADR
from domain.events import DomainEvent


def rehydrate_adr(events: Sequence[DomainEvent]) -> ADR | None:
    """Fold an ordered event stream into an ``ADR`` via ``ADR.restore``."""
    return ADR.restore(events)
