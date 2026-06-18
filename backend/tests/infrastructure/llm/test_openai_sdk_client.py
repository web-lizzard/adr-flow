"""OpenAI SDK completion client tests."""

import asyncio
import json
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import APIStatusError, BadRequestError

from application.ports.llm_completion import ChatMessage
from domain.adr.review_llm_schema import ReviewAnnotationPayload, ReviewPayload
from domain.adr.value_objects import ReviewAnnotationKind
from infrastructure.llm.errors import LlmParseError, LlmProviderError
from infrastructure.llm.openai_sdk_client import OpenAiSdkCompletionClient


def _valid_payload() -> ReviewPayload:
    return ReviewPayload(
        annotations=(
            ReviewAnnotationPayload(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="Status may not reflect the decision.",
                location="## Status",
            ),
        )
    )


def _parse_response(parsed: ReviewPayload) -> MagicMock:
    choice = MagicMock()
    choice.message.parsed = parsed
    response = MagicMock()
    response.choices = [choice]
    return response


def _json_object_response(content: object) -> MagicMock:
    choice = MagicMock()
    choice.message.content = (
        json.dumps(content) if isinstance(content, dict) else content
    )
    response = MagicMock()
    response.choices = [choice]
    return response


def _build_client(
    *, parse_side_effect, create_side_effect=None
) -> OpenAiSdkCompletionClient:
    sdk_client = MagicMock()
    sdk_client.chat.completions.parse = AsyncMock(side_effect=parse_side_effect)
    if create_side_effect is not None:
        sdk_client.chat.completions.create = AsyncMock(side_effect=create_side_effect)
    return OpenAiSdkCompletionClient(
        provider="openrouter",
        api_key="or-key",
        model="openai/gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="https://openrouter.ai/api/v1",
        client=sdk_client,
    )


def test_openai_sdk_client_parses_structured_response() -> None:
    payload = _valid_payload()
    client = _build_client(parse_side_effect=[_parse_response(payload)])

    result = asyncio.run(
        client.complete_structured(
            messages=[
                {"role": "system", "content": "Review ADR"},
                {"role": "user", "content": "## Context\n\nWe need a store.\n"},
            ],
            response_model=ReviewPayload,
        )
    )

    assert result == payload
    assert len(result.annotations) == 1
    assert result.annotations[0].kind == ReviewAnnotationKind.INCONSISTENCY


def test_openai_sdk_client_sends_model_and_messages() -> None:
    payload = _valid_payload()
    sdk_client = MagicMock()
    sdk_client.chat.completions.parse = AsyncMock(return_value=_parse_response(payload))
    client = OpenAiSdkCompletionClient(
        provider="openrouter",
        api_key="or-key",
        model="openai/gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="https://openrouter.ai/api/v1",
        client=sdk_client,
    )
    messages: list[ChatMessage] = [
        {"role": "system", "content": "Review ADR"},
        {"role": "user", "content": "## Context\n\nTBD\n"},
    ]

    asyncio.run(
        client.complete_structured(messages=messages, response_model=ReviewPayload)
    )

    parse_mock = sdk_client.chat.completions.parse
    await_args = cast(Any, parse_mock).await_args
    assert await_args is not None
    kwargs = await_args.kwargs
    assert kwargs["model"] == "openai/gpt-4o-mini"
    assert kwargs["messages"] == messages


def test_openai_sdk_client_raises_provider_error_on_api_failure() -> None:
    response = httpx.Response(401, request=httpx.Request("POST", "http://test"))
    error = APIStatusError("unauthorized", response=response, body={"error": "bad key"})
    client = _build_client(parse_side_effect=[error])

    with pytest.raises(LlmProviderError):
        asyncio.run(
            client.complete_structured(
                messages=[{"role": "user", "content": "## Context\n\nTBD\n"}],
                response_model=ReviewPayload,
            )
        )


def test_openai_sdk_client_raises_parse_error_on_invalid_json_object() -> None:
    client = _build_client(
        parse_side_effect=[
            BadRequestError(
                "unsupported json_schema",
                response=httpx.Response(
                    400, request=httpx.Request("POST", "http://test")
                ),
                body={"error": "unsupported"},
            )
        ],
        create_side_effect=[_json_object_response("not-json")],
    )

    with pytest.raises(LlmParseError):
        asyncio.run(
            client.complete_structured(
                messages=[{"role": "user", "content": "## Context\n\nTBD\n"}],
                response_model=ReviewPayload,
            )
        )


def test_openai_sdk_client_falls_back_to_json_object_on_schema_error() -> None:
    payload_dict = {
        "annotations": [
            {
                "kind": "missing_section",
                "message": "Missing Decision section",
                "location": "## Decision",
                "suggestion": "Document the chosen option.",
            }
        ]
    }
    client = _build_client(
        parse_side_effect=[
            BadRequestError(
                "response_format json_schema is not supported",
                response=httpx.Response(
                    400, request=httpx.Request("POST", "http://test")
                ),
                body={"error": "unsupported"},
            )
        ],
        create_side_effect=[_json_object_response(payload_dict)],
    )

    result = asyncio.run(
        client.complete_structured(
            messages=[{"role": "user", "content": "## Context\n\nTBD\n"}],
            response_model=ReviewPayload,
        )
    )

    assert len(result.annotations) == 1
    assert result.annotations[0].kind == ReviewAnnotationKind.MISSING_SECTION
    create_mock = client._client.chat.completions.create
    assert len(cast(Any, create_mock).await_args_list) == 1
