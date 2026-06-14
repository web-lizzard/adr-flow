from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserId:
    value: UUID


@dataclass(frozen=True, slots=True)
class EmailAddress:
    value: str


@dataclass(frozen=True, slots=True)
class PasswordHash:
    value: str
