"""Parse structured LLM review JSON into domain ReviewResult."""

from datetime import datetime
from typing import Any, cast

from application.logging import get_logger
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from infrastructure.llm.errors import LlmParseError

_logger = get_logger(__name__)

_REVIEW_SYSTEM_PROMPT = (
    "You review Architecture Decision Records (ADRs). "
    "Return JSON with an annotations array. Each annotation must include "
    "kind (missing_section, inconsistency, or conciseness), message, and "
    "kind-specific fields: missing_section and conciseness require suggestion; "
    "inconsistency and conciseness require location."
)


def review_system_prompt() -> str:
    return _REVIEW_SYSTEM_PROMPT


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

    payload_dict = cast(dict[str, Any], payload)
    raw_annotations = payload_dict.get("annotations")
    if not isinstance(raw_annotations, list):
        raise _parse_error("Review response must include an annotations array")

    annotations: list[ReviewAnnotation] = []
    for index, item in enumerate(raw_annotations):
        if not isinstance(item, dict):
            raise _parse_error(f"Annotation {index} must be an object")
        annotation_item = cast(dict[str, Any], item)
        annotations.append(_parse_annotation(annotation_item, index=index))

    return ReviewResult(
        annotations=tuple(annotations),
        reviewed_at=reviewed_at,
        reviewed_content=markdown,
    )


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


def _parse_annotation(item: dict[str, Any], *, index: int) -> ReviewAnnotation:
    try:
        kind = ReviewAnnotationKind(item["kind"])
        message = item["message"]
    except (KeyError, ValueError, TypeError) as exc:
        raise _parse_error(f"Annotation {index} is missing kind or message") from exc

    if not isinstance(message, str):
        raise _parse_error(f"Annotation {index} message must be a string")

    location = item.get("location")
    suggestion = item.get("suggestion")
    if location is not None and not isinstance(location, str):
        raise _parse_error(f"Annotation {index} location must be a string")
    if suggestion is not None and not isinstance(suggestion, str):
        raise _parse_error(f"Annotation {index} suggestion must be a string")

    return ReviewAnnotation(
        kind=kind,
        message=message,
        location=location,
        suggestion=suggestion,
    )
