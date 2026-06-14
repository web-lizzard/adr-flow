"""User aggregate vocabulary."""

from domain.user.aggregate import User
from domain.user.events import UserRegistered
from domain.user.value_objects import EmailAddress, PasswordHash, UserId

__all__ = [
    "EmailAddress",
    "PasswordHash",
    "User",
    "UserId",
    "UserRegistered",
]
