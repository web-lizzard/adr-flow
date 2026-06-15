"""ADR value-object validation errors."""

from domain.errors import ValueObjectError


class InvalidAdrId(ValueObjectError):
    pass


class InvalidAdrTitle(ValueObjectError):
    pass


class InvalidAdrContent(ValueObjectError):
    pass


class InvalidReviewAnnotation(ValueObjectError):
    pass


class InvalidReviewResult(ValueObjectError):
    pass
