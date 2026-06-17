"""Parse structured LLM review JSON into domain ReviewResult."""

from datetime import datetime
from typing import Any, cast

from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from infrastructure.llm.errors import LlmParseError

_REVIEW_SYSTEM_PROMPT = (
    "You review Architecture Decision Records (ADRs). "
    "Return JSON with an annotations array. Each annotation must include "
    "kind (missing_section, inconsistency, or conciseness), message, and "
    "kind-specific fields: missing_section and conciseness require suggestion; "
    "inconsistency and conciseness require location."
)


def review_system_prompt() -> str:
    return _REVIEW_SYSTEM_PROMPT


def parse_review_payload(
    payload: object,
    *,
    markdown: str,
    reviewed_at: datetime,
) -> ReviewResult:
    if not isinstance(payload, dict):
        msg = "Review response must be a JSON object"
        raise LlmParseError(msg)

    payload_dict = cast(dict[str, Any], payload)
    raw_annotations = payload_dict.get("annotations")
    if not isinstance(raw_annotations, list):
        msg = "Review response must include an annotations array"
        raise LlmParseError(msg)

    annotations: list[ReviewAnnotation] = []
    for index, item in enumerate(raw_annotations):
        if not isinstance(item, dict):
            msg = f"Annotation {index} must be an object"
            raise LlmParseError(msg)
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
        msg = "Unexpected chat completion response shape"
        raise LlmParseError(msg) from exc

    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        msg = "Completion content must be a JSON string or object"
        raise LlmParseError(msg)

    import json

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        msg = "Completion content is not valid JSON"
        raise LlmParseError(msg) from exc


def _parse_annotation(item: dict[str, Any], *, index: int) -> ReviewAnnotation:
    try:
        kind = ReviewAnnotationKind(item["kind"])
        message = item["message"]
    except (KeyError, ValueError, TypeError) as exc:
        msg = f"Annotation {index} is missing kind or message"
        raise LlmParseError(msg) from exc

    if not isinstance(message, str):
        msg = f"Annotation {index} message must be a string"
        raise LlmParseError(msg)

    location = item.get("location")
    suggestion = item.get("suggestion")
    if location is not None and not isinstance(location, str):
        msg = f"Annotation {index} location must be a string"
        raise LlmParseError(msg)
    if suggestion is not None and not isinstance(suggestion, str):
        msg = f"Annotation {index} suggestion must be a string"
        raise LlmParseError(msg)

    return ReviewAnnotation(
        kind=kind,
        message=message,
        location=location,
        suggestion=suggestion,
    )
