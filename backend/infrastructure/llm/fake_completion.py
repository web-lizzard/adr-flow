"""Deterministic fake LLM completion port for local development and tests."""

from typing import TypeVar

from pydantic import BaseModel

from application.logging import get_logger
from application.ports.llm_completion import ChatMessage
from domain.adr.required_sections import SectionName
from domain.adr.review_llm_schema import (
    CrossSectionReviewPayload,
    ReviewAnnotationPayload,
    ReviewPayload,
    SectionReviewPayload,
)
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
        if response_model is SectionReviewPayload:
            section = _section_from_system_prompt(_system_content(messages))
            body = _section_body_from_user_message(messages)
            payload = SectionReviewPayload(
                section=section,
                score=_heuristic_score(body),
                feedback=f"Fake review for {section.value} section.",
                annotations=_section_annotations(section, body, messages),
            )
            result = response_model.model_validate(payload.model_dump())
            _logger.info(
                "llm.review.section_parsed",
                section=section.value,
                score=payload.score,
            )
            return result

        if response_model is CrossSectionReviewPayload:
            markdown = _user_content(messages)
            annotations = _cross_section_annotations(markdown)
            payload = CrossSectionReviewPayload(annotations=tuple(annotations))
            result = response_model.model_validate(payload.model_dump())
            _logger.info(
                "llm.review.cross_section_parsed",
                annotation_count=len(payload.annotations),
            )
            return result

        markdown = _user_content(messages)
        payload = ReviewPayload(annotations=tuple(_legacy_annotations(markdown)))
        result = response_model.model_validate(payload.model_dump())
        _logger.info(
            "llm.review.parsed",
            annotation_count=len(payload.annotations),
            output=payload.model_dump(),
        )
        return result


def _heuristic_score(body: str) -> int:
    word_count = len(body.split())
    if word_count < 5:
        return 2
    if word_count < 15:
        return 3
    if word_count < 30:
        return 4
    return 5


def _section_annotations(
    section: SectionName,
    body: str,
    messages: list[ChatMessage],
) -> tuple[ReviewAnnotationPayload, ...]:
    if section is not SectionName.CONTEXT:
        return ()
    doc_markdown = _full_doc_from_user_message(messages)
    if doc_markdown is None or len(doc_markdown) <= 500:
        return ()
    return (
        ReviewAnnotationPayload(
            kind=ReviewAnnotationKind.CONCISENESS,
            message="ADR body is longer than needed for an MVP draft.",
            location="## Context",
            suggestion="Trim background detail to the decision-critical facts.",
        ),
    )


def _cross_section_annotations(markdown: str) -> list[ReviewAnnotationPayload]:
    annotations: list[ReviewAnnotationPayload] = []
    if "## Decision" in markdown and "## Status" in markdown:
        annotations.append(
            ReviewAnnotationPayload(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="Status may not reflect the recorded decision.",
                location="## Status",
            )
        )
    return annotations


def _legacy_annotations(markdown: str) -> list[ReviewAnnotationPayload]:
    return list(_cross_section_annotations(markdown))


def _system_content(messages: list[ChatMessage]) -> str:
    for message in messages:
        if message["role"] == "system":
            return message["content"]
    msg = "Fake completion requires a system message"
    raise ValueError(msg)


def _section_from_system_prompt(system_content: str) -> SectionName:
    for section in SectionName:
        if f"ADR {section.value} section" in system_content:
            return section
    msg = "Fake completion could not determine section scope from system prompt"
    raise ValueError(msg)


def _section_body_from_user_message(messages: list[ChatMessage]) -> str:
    user_content = _user_content(messages)
    marker = "return JSON as specified:"
    if marker in user_content:
        return user_content.split(marker, maxsplit=1)[1].strip().split("\n\n")[0]
    return user_content


def _full_doc_from_user_message(messages: list[ChatMessage]) -> str | None:
    user_content = _user_content(messages)
    marker = "Full ADR markdown (for conciseness/length context):"
    if marker not in user_content:
        return None
    return user_content.split(marker, maxsplit=1)[1].strip()


def _user_content(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message["role"] == "user":
            return message["content"]
    msg = "Fake completion requires a user message with ADR markdown"
    raise ValueError(msg)
