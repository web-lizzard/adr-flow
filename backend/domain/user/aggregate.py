"""User aggregate — command-path state."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from domain.events import DomainEvent
from domain.user.events import UserRegistered
from domain.user.value_objects import EmailAddress, PasswordHash, UserId


@dataclass(frozen=True, slots=True)
class User:
    """Registered user state for command handlers and event replay."""

    user_id: UserId
    email: EmailAddress
    password_hash: PasswordHash
    created_at: datetime

    @classmethod
    def create(
        cls,
        user_id: UserId,
        email: EmailAddress,
        password_hash: PasswordHash,
        created_at: datetime,
    ) -> User:
        """Bootstrap a new user (no prior event stream)."""
        return cls(
            user_id=user_id,
            email=email,
            password_hash=password_hash,
            created_at=created_at,
        )

    @classmethod
    def restore(cls, events: Sequence[DomainEvent]) -> User | None:
        """Fold an ordered event stream into aggregate state.

        Returns ``None`` for an empty stream. Raises ``ValueError`` for unknown
        event types.
        """
        if not events:
            return None

        user: User | None = None
        for event in events:
            match event:
                case UserRegistered():
                    user = cls.create(
                        user_id=event.user_id,
                        email=event.email,
                        password_hash=event.password_hash,
                        created_at=event.occurred_at,
                    )
                case _:
                    msg = f"Unknown event type: {type(event).__name__}"
                    raise ValueError(msg)
        return user
