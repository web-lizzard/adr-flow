"""Tests for Pydantic-to-domain validation mapping."""

import pytest
from pydantic import BaseModel, ValidationError, field_validator

from application.validation import value_error_from_pydantic
from domain.user.errors import InvalidEmailAddress


class _SampleValue(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            msg = "Value is required"
            raise ValueError(msg)
        return value


def test_value_error_from_pydantic_uses_specific_domain_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _SampleValue(value="   ")

    domain_error = value_error_from_pydantic(exc_info.value, InvalidEmailAddress)

    assert isinstance(domain_error, InvalidEmailAddress)
    assert domain_error.kind == "invalid_email_address"
    assert domain_error.message == "Value is required"


def test_value_error_from_pydantic_falls_back_when_errors_empty() -> None:
    domain_error = value_error_from_pydantic(
        ValidationError.from_exception_data("", []),
        InvalidEmailAddress,
    )

    assert domain_error.message == "Invalid value"
