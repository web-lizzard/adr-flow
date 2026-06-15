from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class PasswordHash(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str

    def __init__(self, value: str) -> None:
        super().__init__(value=value)
