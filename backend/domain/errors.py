"""Domain exceptions raised by command and query handlers."""

import re
from typing import ClassVar


def _class_name_to_kind(name: str) -> str:
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


class DomainError(Exception):
    kind: ClassVar[str]
    message: str | None

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        cls.kind = _class_name_to_kind(cls.__name__)

    def __init__(self, message: str | None = None) -> None:
        self.message = message
        super().__init__(message if message is not None else self.kind)


class ValueObjectError(DomainError):
    pass


class EmailAlreadyTaken(DomainError):
    pass


class InvalidCredentials(DomainError):
    pass


class UserNotFound(DomainError):
    pass


class AdrNotFound(DomainError):
    pass


class AdrAccessDenied(DomainError):
    pass


class AdrTitleAlreadyExists(DomainError):
    pass
