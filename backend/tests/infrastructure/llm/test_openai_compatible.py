"""OpenAI-compatible LLM reviewer adapter tests."""

import asyncio
import json
from typing import Any, cast

import httpx
import pytest

from domain.adr.value_objects import ReviewAnnotationKind
from infrastructure.llm.errors import LlmParseError, LlmProviderError
from infrastructure.llm.openai_compatible import OpenAiCompatibleReviewer


def _valid_payload() -> dict:
    return {
        "annotations": [
            {
                "kind": "missing_section",
                "message": "Missing Decision section",
                "location": "## Decision",
                "suggestion": "Document the chosen option.",
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


def test_openai_compatible_reviewer_parses_successful_response() -> None:
    markdown = "## Context\n\nWe need a store.\n"
    transport = httpx.MockTransport(
        lambda request: _completion_response(_valid_payload())
    )
    client = httpx.AsyncClient(
        transport=transport,
        base_url="http://llm.test/v1",
    )
    reviewer = OpenAiCompatibleReviewer(
        base_url="http://llm.test/v1",
        api_key="test-key",
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        client=client,
    )

    result = asyncio.run(reviewer.review(markdown))

    assert result.reviewed_content == markdown
    assert len(result.annotations) == 1
    assert result.annotations[0].kind == ReviewAnnotationKind.MISSING_SECTION


def test_openai_compatible_reviewer_sends_model_and_auth(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode())
        return _completion_response(_valid_payload())

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://llm.test/v1")
    reviewer = OpenAiCompatibleReviewer(
        base_url="http://llm.test/v1",
        api_key="local-key",
        model="local-model",
        timeout_seconds=5.0,
        client=client,
    )

    asyncio.run(reviewer.review("## Context\n\nTBD\n"))

    assert captured["url"] == "http://llm.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer local-key"
    body = cast(dict[str, Any], captured["body"])
    assert body.get("model") == "local-model"


def test_openai_compatible_reviewer_raises_provider_error_on_http_failure() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(503, json={"error": "unavailable"})
    )
    client = httpx.AsyncClient(transport=transport, base_url="http://llm.test/v1")
    reviewer = OpenAiCompatibleReviewer(
        base_url="http://llm.test/v1",
        api_key=None,
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        client=client,
    )

    with pytest.raises(LlmProviderError):
        asyncio.run(reviewer.review("## Context\n\nTBD\n"))


def test_openai_compatible_reviewer_raises_parse_error_on_invalid_json() -> None:
    transport = httpx.MockTransport(lambda _request: _completion_response("not-json"))
    client = httpx.AsyncClient(transport=transport, base_url="http://llm.test/v1")
    reviewer = OpenAiCompatibleReviewer(
        base_url="http://llm.test/v1",
        api_key=None,
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        client=client,
    )

    with pytest.raises(LlmParseError):
        asyncio.run(reviewer.review("## Context\n\nTBD\n"))
