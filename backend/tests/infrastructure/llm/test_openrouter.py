"""OpenRouter LLM reviewer adapter tests."""

import asyncio
import json
from typing import Any, cast

import httpx
import pytest

from domain.adr.value_objects import ReviewAnnotationKind
from infrastructure.llm.errors import LlmParseError, LlmProviderError
from infrastructure.llm.openrouter import OpenRouterReviewer


def _valid_payload() -> dict:
    return {
        "annotations": [
            {
                "kind": "inconsistency",
                "message": "Status may not reflect the decision.",
                "location": "## Status",
            }
        ]
    }


def _completion_response(content: object) -> httpx.Response:
    body = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content)
                    if isinstance(content, dict)
                    else content,
                }
            }
        ]
    }
    return httpx.Response(200, json=body)


def test_openrouter_reviewer_parses_successful_response() -> None:
    markdown = "## Context\n\nWe need a store.\n"
    transport = httpx.MockTransport(
        lambda request: _completion_response(_valid_payload())
    )
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://openrouter.ai/api/v1",
    )
    reviewer = OpenRouterReviewer(
        api_key="or-key",
        model="anthropic/claude-3.5-sonnet",
        timeout_seconds=5.0,
        client=client,
    )

    result = asyncio.run(reviewer.review(markdown))

    assert result.reviewed_content == markdown
    assert len(result.annotations) == 1
    assert result.annotations[0].kind == ReviewAnnotationKind.INCONSISTENCY


def test_openrouter_reviewer_sends_authorization_and_model() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode())
        return _completion_response(_valid_payload())

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://openrouter.ai/api/v1",
    )
    reviewer = OpenRouterReviewer(
        api_key="or-key",
        model="openai/gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="https://custom.openrouter.test/v1",
        client=client,
    )

    asyncio.run(reviewer.review("## Context\n\nTBD\n"))

    assert captured["url"] == "https://custom.openrouter.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer or-key"
    body = cast(dict[str, Any], captured["body"])
    assert body.get("model") == "openai/gpt-4o-mini"


def test_openrouter_reviewer_raises_provider_error_on_http_failure() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(401, json={"error": "unauthorized"})
    )
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://openrouter.ai/api/v1",
    )
    reviewer = OpenRouterReviewer(
        api_key="bad-key",
        model="openai/gpt-4o-mini",
        timeout_seconds=5.0,
        client=client,
    )

    with pytest.raises(LlmProviderError):
        asyncio.run(reviewer.review("## Context\n\nTBD\n"))


def test_openrouter_reviewer_raises_parse_error_on_missing_annotations() -> None:
    transport = httpx.MockTransport(
        lambda _request: _completion_response({"notes": "no annotations key"})
    )
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://openrouter.ai/api/v1",
    )
    reviewer = OpenRouterReviewer(
        api_key="or-key",
        model="openai/gpt-4o-mini",
        timeout_seconds=5.0,
        client=client,
    )

    with pytest.raises(LlmParseError):
        asyncio.run(reviewer.review("## Context\n\nTBD\n"))
