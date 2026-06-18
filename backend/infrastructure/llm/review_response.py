"""Parse structured LLM review JSON into domain ReviewResult."""

from datetime import datetime
from typing import Any, cast

from pydantic import ValidationError

from application.logging import get_logger
from domain.adr.review_instructions import build_review_system_prompt
from domain.adr.review_llm_schema import ReviewPayload, to_review_result
from domain.adr.value_objects import ReviewResult
from infrastructure.llm.errors import LlmParseError

_logger = get_logger(__name__)


def review_system_prompt() -> str:
    return build_review_system_prompt()


def _parse_error(reason: str) -> LlmParseError:
    _logger.debug("llm.review.parse_validation_failed", reason=reason)
    return LlmParseError(reason)


def parse_review_payload(
    payload: object,
    *,
    markdown: str,
    reviewed_at: datetime,
) -> ReviewResult:
    if not isinstance(payload, dict):
        raise _parse_error("Review response must be a JSON object")

    try:
        validated = ReviewPayload.model_validate(cast(dict[str, Any], payload))
    except ValidationError as exc:
        raise _parse_error("Review response failed schema validation") from exc

    return to_review_result(validated, markdown=markdown, reviewed_at=reviewed_at)


def extract_json_content(completion_body: dict[str, Any]) -> object:
    try:
        choices = completion_body["choices"]
        message = choices[0]["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise _parse_error("Unexpected chat completion response shape") from exc

    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise _parse_error("Completion content must be a JSON string or object")

    import json

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise _parse_error("Completion content is not valid JSON") from exc
