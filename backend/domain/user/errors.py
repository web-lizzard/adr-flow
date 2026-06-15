"""User value-object validation errors."""

from domain.errors import ValueObjectError


class InvalidEmailAddress(ValueObjectError):
    pass
