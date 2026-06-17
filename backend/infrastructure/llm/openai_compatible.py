"""OpenAI-compatible chat-completions reviewer adapter."""

from datetime import UTC, datetime

import httpx

from application.ports.llm_reviewer import LlmReviewer
from domain.adr.value_objects import ReviewResult
from infrastructure.llm.errors import LlmProviderError, LlmParseError
from infrastructure.llm.review_response import (
    extract_json_content,
    parse_review_payload,
    review_system_prompt,
)


class OpenAiCompatibleReviewer(LlmReviewer):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._client = client

    async def review(self, markdown: str) -> ReviewResult:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": review_system_prompt()},
                {"role": "user", "content": markdown},
            ],
            "response_format": {"type": "json_object"},
        }

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
            msg = f"OpenAI-compatible review request failed: {exc}"
            raise LlmProviderError(msg) from exc

        if response.status_code >= 400:
            msg = f"OpenAI-compatible review request failed with status {response.status_code}"
            raise LlmProviderError(msg)

        try:
            body = response.json()
            parsed = extract_json_content(body)
            return parse_review_payload(
                parsed,
                markdown=markdown,
                reviewed_at=datetime.now(UTC),
            )
        except LlmParseError:
            raise
        except Exception as exc:
            msg = "Failed to parse OpenAI-compatible review response"
            raise LlmParseError(msg) from exc
