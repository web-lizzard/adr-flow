"""OpenAI SDK completion client — thin transport adapter."""

import time
from typing import TypeVar, cast

from openai import APIStatusError, AsyncOpenAI, BadRequestError, OpenAIError
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from application.logging import get_logger
from application.ports.llm_completion import ChatMessage
from infrastructure.llm.errors import LlmParseError, LlmProviderError

T = TypeVar("T", bound=BaseModel)

_logger = get_logger(__name__)
_SCHEMA_ERROR_MARKERS = ("json_schema", "response_format", "strict")


class OpenAiSdkCompletionClient:
    def __init__(
        self,
        *,
        provider: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
        base_url: str,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    async def complete_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T:
        markdown_length = _user_message_length(messages)
        _logger.info(
            "llm.review.request_started",
            provider=self._provider,
            model=self._model,
            markdown_length=markdown_length,
        )
        start = time.perf_counter()
        sdk_messages = cast(list[ChatCompletionMessageParam], messages)
        try:
            completion = await self._client.chat.completions.parse(
                model=self._model,
                messages=sdk_messages,
                response_format=response_model,
            )
        except BadRequestError as exc:
            if _is_schema_error(exc):
                _logger.warning(
                    "llm.review.structured_output_fallback",
                    provider=self._provider,
                    model=self._model,
                )
                return await self._complete_via_json_object(
                    messages=messages,
                    response_model=response_model,
                    start=start,
                )
            _log_api_error(exc, start)
            msg = f"LLM completion request failed: {exc}"
            raise LlmProviderError(msg) from exc
        except APIStatusError as exc:
            _log_api_error(exc, start)
            msg = f"LLM completion request failed: {exc}"
            raise LlmProviderError(msg) from exc
        except OpenAIError as exc:
            _logger.error(
                "llm.review.http_error",
                error_type=type(exc).__name__,
            )
            msg = f"LLM completion request failed: {exc}"
            raise LlmProviderError(msg) from exc

        duration_ms = round((time.perf_counter() - start) * 1000)
        _logger.info(
            "llm.review.http_completed",
            status_code=200,
            duration_ms=duration_ms,
        )

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            msg = "Structured parse returned no parsed object"
            raise LlmParseError(msg)

        _log_parsed(parsed)
        return parsed

    async def _complete_via_json_object(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
        start: float,
    ) -> T:
        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=cast(list[ChatCompletionMessageParam], messages),
                response_format={"type": "json_object"},
            )
        except APIStatusError as exc:
            _log_api_error(exc, start)
            msg = f"LLM completion request failed: {exc}"
            raise LlmProviderError(msg) from exc
        except OpenAIError as exc:
            _logger.error(
                "llm.review.http_error",
                error_type=type(exc).__name__,
            )
            msg = f"LLM completion request failed: {exc}"
            raise LlmProviderError(msg) from exc

        duration_ms = round((time.perf_counter() - start) * 1000)
        _logger.info(
            "llm.review.http_completed",
            status_code=200,
            duration_ms=duration_ms,
        )

        content = completion.choices[0].message.content
        if not content:
            msg = "JSON object completion returned empty content"
            raise LlmParseError(msg)

        try:
            result = response_model.model_validate_json(content)
        except ValidationError as exc:
            msg = "Failed to parse LLM JSON object response"
            raise LlmParseError(msg) from exc

        _log_parsed(result)
        return result


def _user_message_length(messages: list[ChatMessage]) -> int:
    for message in reversed(messages):
        if message["role"] == "user":
            return len(message["content"])
    return 0


def _is_schema_error(exc: BadRequestError) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _SCHEMA_ERROR_MARKERS)


def _log_api_error(exc: APIStatusError | BadRequestError, start: float) -> None:
    duration_ms = round((time.perf_counter() - start) * 1000)
    status_code = exc.response.status_code if exc.response is not None else None
    _logger.error(
        "llm.review.http_error",
        error_type=type(exc).__name__,
        status_code=status_code,
        duration_ms=duration_ms,
    )


def _log_parsed(parsed: BaseModel) -> None:
    annotation_count = None
    annotations = getattr(parsed, "annotations", None)
    if annotations is not None:
        annotation_count = len(annotations)
    _logger.info("llm.review.parsed", annotation_count=annotation_count)
