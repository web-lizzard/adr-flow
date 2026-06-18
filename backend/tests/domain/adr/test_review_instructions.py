"""Domain review instruction builder tests."""

from domain.adr import SectionName
from domain.adr.review_instructions import (
    build_review_system_prompt,
    build_review_user_message,
)

_PLACEHOLDER_TOKENS = ("tbd", "todo", "n/a")


def test_system_prompt_lists_all_required_sections() -> None:
    prompt = build_review_system_prompt()

    for section in SectionName:
        assert section.value in prompt


def test_system_prompt_describes_placeholder_rules() -> None:
    prompt = build_review_system_prompt().casefold()

    for token in _PLACEHOLDER_TOKENS:
        assert token in prompt


def test_system_prompt_includes_per_kind_actionability_criteria() -> None:
    prompt = build_review_system_prompt().casefold()

    assert "missing_section" in prompt
    assert "inconsistency" in prompt
    assert "conciseness" in prompt
    assert "suggestion" in prompt
    assert "location" in prompt
    assert "one missing_section annotation per gap" in prompt or (
        "one" in prompt and "missing_section" in prompt
    )


def test_system_prompt_includes_inconsistency_and_conciseness_product_rules() -> None:
    prompt = build_review_system_prompt().casefold()

    assert "decision" in prompt and "status" in prompt
    assert "verbose" in prompt or "concise" in prompt or "length" in prompt


def test_user_message_wraps_adr_markdown() -> None:
    markdown = "## Context\n\nWe need a store.\n"

    user_message = build_review_user_message(markdown)

    assert markdown in user_message
    assert "adr" in user_message.casefold()
