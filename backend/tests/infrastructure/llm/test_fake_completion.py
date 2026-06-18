"""Fake LLM completion port tests."""

import asyncio

from domain.adr.review_llm_schema import ReviewPayload
from domain.adr.value_objects import ReviewAnnotationKind
from infrastructure.llm.fake_completion import FakeLlmCompletionPort


def test_fake_completion_returns_missing_section_annotations() -> None:
    markdown = "## Context\n\nWe need a store.\n"
    port = FakeLlmCompletionPort()

    payload = asyncio.run(
        port.complete_structured(
            messages=[{"role": "user", "content": markdown}],
            response_model=ReviewPayload,
        )
    )

    kinds = {item.kind for item in payload.annotations}
    assert ReviewAnnotationKind.MISSING_SECTION in kinds
    assert len(payload.annotations) >= 4


def test_fake_completion_returns_inconsistency_when_decision_and_status_present() -> (
    None
):
    markdown = (
        "## Context\n\nWe need a store.\n"
        "## Options\n\nA or B.\n"
        "## Decision\n\nChoose A.\n"
        "## Status\n\nAccepted.\n"
        "## Consequences\n\nWe ship A.\n"
    )
    port = FakeLlmCompletionPort()

    payload = asyncio.run(
        port.complete_structured(
            messages=[{"role": "user", "content": markdown}],
            response_model=ReviewPayload,
        )
    )

    kinds = {item.kind for item in payload.annotations}
    assert ReviewAnnotationKind.INCONSISTENCY in kinds


def test_fake_completion_returns_conciseness_for_long_body() -> None:
    markdown = "## Context\n\n" + ("word " * 200)
    port = FakeLlmCompletionPort()

    payload = asyncio.run(
        port.complete_structured(
            messages=[{"role": "user", "content": markdown}],
            response_model=ReviewPayload,
        )
    )

    kinds = {item.kind for item in payload.annotations}
    assert ReviewAnnotationKind.CONCISENESS in kinds
