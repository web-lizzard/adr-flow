"""Rate-limit retry delay tests."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from openai import APIStatusError

from infrastructure.llm.errors import LlmProviderError
from infrastructure.llm.rate_limit import (
    parse_rate_limit_reset_ms,
    rate_limit_reset_at_from_api_error,
    rate_limit_reset_from_error,
    retry_delay_seconds,
)


def test_parse_rate_limit_reset_ms_accepts_milliseconds() -> None:
    assert parse_rate_limit_reset_ms("1783184040000") == 1783184040000


def test_parse_rate_limit_reset_ms_accepts_seconds() -> None:
    assert parse_rate_limit_reset_ms("1783184040") == 1783184040000


def test_rate_limit_reset_at_from_response_header() -> None:
    reset_ms = int((datetime.now(UTC) + timedelta(seconds=30)).timestamp() * 1000)
    response = httpx.Response(
        429,
        request=httpx.Request("POST", "http://test"),
        headers={"X-RateLimit-Reset": str(reset_ms)},
    )
    error = APIStatusError("rate limited", response=response, body={"error": "limit"})

    reset_at = rate_limit_reset_at_from_api_error(error)

    assert reset_at == datetime.fromtimestamp(reset_ms / 1000, tz=UTC)


def test_rate_limit_reset_at_from_error_body_metadata() -> None:
    reset_ms = int((datetime.now(UTC) + timedelta(seconds=45)).timestamp() * 1000)
    response = httpx.Response(429, request=httpx.Request("POST", "http://test"))
    error = APIStatusError(
        "rate limited",
        response=response,
        body={
            "error": {
                "message": "Rate limit exceeded",
                "metadata": {
                    "headers": {
                        "X-RateLimit-Reset": str(reset_ms),
                    }
                },
            }
        },
    )

    reset_at = rate_limit_reset_at_from_api_error(error)

    assert reset_at == datetime.fromtimestamp(reset_ms / 1000, tz=UTC)


def test_retry_delay_uses_reset_header_plus_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 4, 16, 0, 0, tzinfo=UTC)
    reset_at = now + timedelta(seconds=20)
    error = LlmProviderError("429 rate limit", rate_limit_reset_at=reset_at)
    monkeypatch.setattr(
        "infrastructure.llm.rate_limit.random.uniform",
        lambda _low, _high: 1.5,
    )

    delay = retry_delay_seconds(
        0,
        base_seconds=2.0,
        error=error,
        now=now,
    )

    assert delay == pytest.approx(21.5)


def test_rate_limit_reset_from_error_message_fallback() -> None:
    reset_ms = 1783184040000
    error = LlmProviderError(
        "Error code: 429 - {'metadata': {'headers': {'X-RateLimit-Reset': "
        f"'{reset_ms}'}}}}",
    )

    reset_at = rate_limit_reset_from_error(error)

    assert reset_at == datetime.fromtimestamp(reset_ms / 1000, tz=UTC)
