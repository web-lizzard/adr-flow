"""Deterministic fake LLM completion port for local development and tests."""

from typing import TypeVar

from pydantic import BaseModel

from application.logging import get_logger
from application.ports.llm_completion import ChatMessage
from domain.adr import find_missing_or_empty_sections
from domain.adr.review_llm_schema import ReviewAnnotationPayload, ReviewPayload
from domain.adr.value_objects import ReviewAnnotationKind

T = TypeVar("T", bound=BaseModel)

_logger = get_logger(__name__)


class FakeLlmCompletionPort:
    async def complete_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[T],
    ) -> T:
        markdown = _user_content(messages)
        annotations: list[ReviewAnnotationPayload] = []

        missing = find_missing_or_empty_sections(markdown)
        for section in sorted(missing, key=lambda item: item.value):
            annotations.append(
                ReviewAnnotationPayload(
                    kind=ReviewAnnotationKind.MISSING_SECTION,
                    message=f"Missing {section.value} section",
                    location=f"## {section.value}",
                    suggestion=f"Add content for the {section.value} section.",
                )
            )

        if "## Decision" in markdown and "## Status" in markdown:
            annotations.append(
                ReviewAnnotationPayload(
                    kind=ReviewAnnotationKind.INCONSISTENCY,
                    message="Status may not reflect the recorded decision.",
                    location="## Status",
                )
            )

        if len(markdown) > 500:
            annotations.append(
                ReviewAnnotationPayload(
                    kind=ReviewAnnotationKind.CONCISENESS,
                    message="ADR body is longer than needed for an MVP draft.",
                    location="## Context",
                    suggestion="Trim background detail to the decision-critical facts.",
                )
            )

        payload = ReviewPayload(annotations=tuple(annotations))
        result = response_model.model_validate(payload.model_dump())
        _logger.info(
            "llm.review.parsed",
            annotation_count=len(payload.annotations),
            output=payload.model_dump(),
        )
        return result


def _user_content(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message["role"] == "user":
            return message["content"]
    msg = "Fake completion requires a user message with ADR markdown"
    raise ValueError(msg)
