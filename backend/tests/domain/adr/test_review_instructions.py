"""Domain review instruction builder tests."""

import pytest

from domain.adr import SectionName
from domain.adr.review_instructions import (
    build_cross_section_system_prompt,
    build_section_system_prompt,
    build_section_user_message,
)

_PLACEHOLDER_TOKENS = ("tbd", "todo", "n/a")


@pytest.mark.parametrize("section", list(SectionName))
def test_section_system_prompt_lists_target_section(section: SectionName) -> None:
    prompt = build_section_system_prompt(section)

    assert section.value in prompt


@pytest.mark.parametrize("section", list(SectionName))
def test_section_system_prompt_excludes_missing_section_instructions(
    section: SectionName,
) -> None:
    prompt = build_section_system_prompt(section).casefold()

    assert "one missing_section annotation per gap" not in prompt
    assert "treat a section as missing" not in prompt
    assert "gaps are detected before your call" in prompt


@pytest.mark.parametrize("section", list(SectionName))
def test_section_system_prompt_includes_universal_rubric_anchors(
    section: SectionName,
) -> None:
    prompt = build_section_system_prompt(section).casefold()

    for anchor in ("score 1", "score 2", "score 3", "score 4", "score 5"):
        assert anchor in prompt


def test_cross_section_system_prompt_covers_decision_status_inconsistency() -> None:
    prompt = build_cross_section_system_prompt().casefold()

    assert "decision" in prompt
    assert "status" in prompt
    assert "inconsistency" in prompt
    assert "treat a section as missing" not in prompt
    assert "gaps are detected before your call" in prompt


def test_section_user_message_includes_section_body() -> None:
    body = "We need a database for the project."

    message = build_section_user_message(SectionName.CONTEXT, body)

    assert body in message
    assert SectionName.CONTEXT.value in message


def test_context_user_message_includes_full_document_for_conciseness() -> None:
    body = "We need a database."
    doc_markdown = f"## Context\n\n{body}\n\n## Options\n\nPostgreSQL vs MongoDB.\n"

    message = build_section_user_message(
        SectionName.CONTEXT,
        body,
        doc_markdown=doc_markdown,
    )

    assert "## Options" in message
    assert "concise" in message.casefold() or "length" in message.casefold()


def test_non_context_user_message_omits_doc_markdown_hint() -> None:
    body = "We will use PostgreSQL."
    doc_markdown = "## Context\n\nLong context.\n"

    message = build_section_user_message(
        SectionName.DECISION,
        body,
        doc_markdown=doc_markdown,
    )

    assert body in message
    assert "## Context" not in message
