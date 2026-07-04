"""Fake LLM completion port tests."""

import asyncio

from domain.adr.required_sections import SectionName
from domain.adr.review_instructions import (
    build_cross_section_system_prompt,
    build_cross_section_user_message,
    build_section_system_prompt,
    build_section_user_message,
)
from domain.adr.review_llm_schema import (
    CrossSectionReviewPayload,
    SectionReviewPayload,
)
from domain.adr.value_objects import ReviewAnnotationKind
from infrastructure.llm.fake_completion import FakeLlmCompletionPort
from tests.review_quality.cases import load_fixture


def test_fake_completion_returns_section_rating_payload() -> None:
    section = SectionName.CONTEXT
    body = "We need a database for the project."
    port = FakeLlmCompletionPort()

    payload = asyncio.run(
        port.complete_structured(
            messages=[
                {"role": "system", "content": build_section_system_prompt(section)},
                {
                    "role": "user",
                    "content": build_section_user_message(section, body),
                },
            ],
            response_model=SectionReviewPayload,
        )
    )

    assert payload.section is section
    assert 1 <= payload.score <= 5
    assert payload.feedback
    assert all(
        annotation.kind is not ReviewAnnotationKind.MISSING_SECTION
        for annotation in payload.annotations
    )


def test_fake_completion_returns_cross_section_inconsistency() -> None:
    markdown = load_fixture("complete.md")
    port = FakeLlmCompletionPort()

    payload = asyncio.run(
        port.complete_structured(
            messages=[
                {
                    "role": "system",
                    "content": build_cross_section_system_prompt(),
                },
                {"role": "user", "content": build_cross_section_user_message(markdown)},
            ],
            response_model=CrossSectionReviewPayload,
        )
    )

    kinds = {item.kind for item in payload.annotations}
    assert ReviewAnnotationKind.INCONSISTENCY in kinds


def test_fake_completion_returns_conciseness_on_context_with_long_doc() -> None:
    section = SectionName.CONTEXT
    body = "We need a store."
    doc_markdown = "## Context\n\n" + ("word " * 200)
    port = FakeLlmCompletionPort()

    payload = asyncio.run(
        port.complete_structured(
            messages=[
                {"role": "system", "content": build_section_system_prompt(section)},
                {
                    "role": "user",
                    "content": build_section_user_message(
                        section,
                        body,
                        doc_markdown=doc_markdown,
                    ),
                },
            ],
            response_model=SectionReviewPayload,
        )
    )

    kinds = {item.kind for item in payload.annotations}
    assert ReviewAnnotationKind.CONCISENESS in kinds
