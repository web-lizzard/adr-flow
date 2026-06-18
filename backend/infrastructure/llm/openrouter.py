"""OpenRouter chat-completions reviewer adapter."""

import time
from datetime import UTC, datetime

import httpx

from application.logging import get_logger
from application.ports.llm_reviewer import LlmReviewer
from domain.adr.value_objects import ReviewResult
from infrastructure.llm.errors import LlmProviderError, LlmParseError
from infrastructure.llm.review_response import (
    extract_json_content,
    parse_review_payload,
    review_system_prompt,
)

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_logger = get_logger(__name__)


class OpenRouterReviewer(LlmReviewer):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._client = client

    async def review(self, markdown: str) -> ReviewResult:
        _logger.info(
            "llm.review.request_started",
            provider="openrouter",
            model=self._model,
            markdown_length=len(markdown),
            timeout_seconds=self._timeout_seconds,
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": review_system_prompt()},
                {"role": "user", "content": markdown},
            ],
            "response_format": {"type": "json_object"},
        }

        start = time.perf_counter()
        try:
            if self._client is not None:
                response = await self._client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=self._timeout_seconds,
                    )
        except httpx.HTTPError as exc:
            _logger.error(
                "llm.review.http_error",
                error_type=type(exc).__name__,
            )
            msg = f"OpenRouter review request failed: {exc}"
            raise LlmProviderError(msg) from exc

        duration_ms = round((time.perf_counter() - start) * 1000)
        if response.status_code >= 400:
            _logger.error(
                "llm.review.http_error",
                error_type="http_status_error",
                status_code=response.status_code,
            )
            msg = f"OpenRouter review request failed with status {response.status_code}"
            raise LlmProviderError(msg)

        _logger.info(
            "llm.review.http_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        try:
            body = response.json()
            parsed = extract_json_content(body)
            result = parse_review_payload(
                parsed,
                markdown=markdown,
                reviewed_at=datetime.now(UTC),
            )
            _logger.info(
                "llm.review.parsed",
                annotation_count=len(result.annotations),
            )
            return result
        except LlmParseError:
            raise
        except Exception as exc:
            msg = "Failed to parse OpenRouter review response"
            raise LlmParseError(msg) from exc
