"""Map Pydantic value-object validation failures to domain errors."""

from pydantic import ValidationError

from domain.errors import DomainError


def value_error_from_pydantic(
    exc: ValidationError,
    error_type: type[DomainError],
) -> DomainError:
    return error_type(_first_error_message(exc))


def _first_error_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid value"
    first = errors[0]
    ctx = first.get("ctx")
    if isinstance(ctx, dict):
        error = ctx.get("error")
        if isinstance(error, Exception) and error.args:
            return str(error.args[0])
    message = first.get("msg", "Invalid value")
    if isinstance(message, str) and message.startswith("Value error, "):
        return message.removeprefix("Value error, ")
    return str(message)
