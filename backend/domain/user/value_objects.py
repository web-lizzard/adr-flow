from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class UserId(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: UUID

    def __init__(self, value: UUID) -> None:
        super().__init__(value=value)


class EmailAddress(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    def __init__(self, value: str) -> None:
        super().__init__(value=value)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or "@" not in normalized:
            msg = "Invalid email address"
            raise ValueError(msg)
        return normalized


class PasswordHash(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    def __init__(self, value: str) -> None:
        super().__init__(value=value)
