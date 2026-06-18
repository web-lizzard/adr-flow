"""User aggregate — command-path state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
