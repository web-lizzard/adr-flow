from dataclasses import dataclass
from datetime import datetime

from domain.user.value_objects import EmailAddress, PasswordHash, UserId


@dataclass(frozen=True, slots=True)
class UserRegistered:
    user_id: UserId
    email: EmailAddress
    password_hash: PasswordHash
    occurred_at: datetime
