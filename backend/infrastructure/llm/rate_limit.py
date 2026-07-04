"""Rate-limit metadata parsing and retry delay calculation."""

from __future__ import annotations

import random
import re
from datetime import UTC, datetime
from typing import cast

from openai import APIStatusError

_RESET_HEADER_PATTERN = re.compile(
    r"""['"]?X-RateLimit-Reset['"]?\s*[:=]\s*['"]?(\d+)""",
    re.IGNORECASE,
)


def parse_rate_limit_reset_ms(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value.strip())
    except ValueError:
        return None
    if parsed <= 0:
        return None
    if parsed > 10_000_000_000:
        return parsed
    return parsed * 1000


def rate_limit_reset_at_from_api_error(exc: APIStatusError) -> datetime | None:
    reset_ms: int | None = None
    if exc.response is not None:
        reset_ms = parse_rate_limit_reset_ms(
            _header_value(exc.response.headers, "x-ratelimit-reset"),
        )
    if reset_ms is None and exc.body is not None:
        reset_ms = _reset_ms_from_api_body(exc.body)
    if reset_ms is None:
        return None
    return datetime.fromtimestamp(reset_ms / 1000, tz=UTC)


def rate_limit_reset_from_error(error: Exception) -> datetime | None:
    from infrastructure.llm.errors import LlmProviderError

    if isinstance(error, LlmProviderError) and error.rate_limit_reset_at is not None:
        return error.rate_limit_reset_at

    cause = error.__cause__
    if isinstance(cause, APIStatusError):
        reset_at = rate_limit_reset_at_from_api_error(cause)
        if reset_at is not None:
            return reset_at

    match = _RESET_HEADER_PATTERN.search(str(error))
    if match is not None:
        reset_ms = parse_rate_limit_reset_ms(match.group(1))
        if reset_ms is not None:
            return datetime.fromtimestamp(reset_ms / 1000, tz=UTC)

    return None


def is_rate_limit_error(error: Exception) -> bool:
    message = str(error).casefold()
    if "429" in message or "rate limit" in message:
        return True
    cause = error.__cause__
    if isinstance(cause, APIStatusError) and cause.response is not None:
        return cause.response.status_code == 429
    return False


def retry_delay_seconds(
    attempt_index: int,
    *,
    base_seconds: float,
    error: Exception,
    now: datetime | None = None,
) -> float:
    reset_at = rate_limit_reset_from_error(error)
    if reset_at is not None:
        current = now or datetime.now(UTC)
        margin = random.uniform(0.5, 3.0)
        return max(0.0, (reset_at - current).total_seconds() + margin)

    delay = base_seconds * (2**attempt_index)
    if is_rate_limit_error(error):
        delay = max(delay, 10.0)
    return delay


def _header_value(headers: object, name: str) -> str | None:
    if headers is None:
        return None
    try:
        return headers.get(name)  # ty: ignore[unresolved-attribute]
    except AttributeError:
        pass
    lowered = name.casefold()
    for key, value in headers.items():  # ty: ignore[unresolved-attribute]
        if str(key).casefold() == lowered:
            return str(value)
    return None


def _reset_ms_from_api_body(body: object) -> int | None:
    if not isinstance(body, dict):
        return None

    payload = cast("dict[str, object]", body)
    candidates: list[dict[str, object]] = [payload]
    error = payload.get("error")
    if isinstance(error, dict):
        candidates.append(cast("dict[str, object]", error))

    for candidate in candidates:
        metadata = candidate.get("metadata")
        if not isinstance(metadata, dict):
            continue
        headers = cast("dict[str, object]", metadata).get("headers")
        if not isinstance(headers, dict):
            continue
        reset_ms = parse_rate_limit_reset_ms(
            str(cast("dict[str, object]", headers).get("X-RateLimit-Reset", ""))
            or None,
        )
        if reset_ms is not None:
            return reset_ms

    return None
