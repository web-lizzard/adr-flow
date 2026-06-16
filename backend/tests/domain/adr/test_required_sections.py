"""Required ADR section parser tests."""

from domain.adr import (
    ADR_STARTER_TEMPLATE,
    SectionName,
    find_missing_or_empty_sections,
    parse_adr_sections,
)

_COMPLETE_ADR = """\
## Context

We need to choose a database for the project.

## Options

1. PostgreSQL
2. MongoDB

## Decision

We will use PostgreSQL.

## Status

Accepted

## Consequences

Positive: ACID compliance. Negative: operational overhead.
"""


def test_complete_adr_returns_empty_set() -> None:
    assert find_missing_or_empty_sections(_COMPLETE_ADR) == frozenset()


def test_missing_single_heading_detected() -> None:
    markdown = _COMPLETE_ADR.replace(
        "## Context\n\nWe need to choose a database for the project.\n\n",
        "",
    )
    assert find_missing_or_empty_sections(markdown) == frozenset({SectionName.CONTEXT})


def test_empty_body_detected() -> None:
    markdown = _COMPLETE_ADR.replace(
        "We will use PostgreSQL.",
        "",
    )
    assert find_missing_or_empty_sections(markdown) == frozenset({SectionName.DECISION})


def test_placeholder_body_detected() -> None:
    markdown = _COMPLETE_ADR.replace("Accepted", "TBD")
    assert find_missing_or_empty_sections(markdown) == frozenset({SectionName.STATUS})


def test_multiple_gaps_detected() -> None:
    markdown = """\
## Context

Still drafting.

## Options


## Decision

TBD

## Status

Accepted

## Consequences

"""
    assert find_missing_or_empty_sections(markdown) == frozenset(
        {
            SectionName.OPTIONS,
            SectionName.DECISION,
            SectionName.CONSEQUENCES,
        }
    )


def test_extra_non_required_sections_ignored() -> None:
    markdown = _COMPLETE_ADR + "\n## References\n\nSome link."
    assert find_missing_or_empty_sections(markdown) == frozenset()


def test_wrong_synonym_alternatives_not_counted_as_options() -> None:
    markdown = _COMPLETE_ADR.replace("## Options", "## Alternatives")
    assert find_missing_or_empty_sections(markdown) == frozenset({SectionName.OPTIONS})


def test_case_mismatch_context_not_matched() -> None:
    markdown = _COMPLETE_ADR.replace("## Context", "## context")
    assert find_missing_or_empty_sections(markdown) == frozenset({SectionName.CONTEXT})


def test_starter_template_flags_all_five_sections() -> None:
    assert find_missing_or_empty_sections(ADR_STARTER_TEMPLATE) == frozenset(
        {
            SectionName.CONTEXT,
            SectionName.OPTIONS,
            SectionName.DECISION,
            SectionName.STATUS,
            SectionName.CONSEQUENCES,
        }
    )


def test_parse_adr_sections_extracts_bodies() -> None:
    parsed = parse_adr_sections(_COMPLETE_ADR)
    assert parsed.body_for(SectionName.CONTEXT) == (
        "We need to choose a database for the project."
    )
    assert parsed.body_for(SectionName.OPTIONS) == "1. PostgreSQL\n2. MongoDB"
    assert parsed.body_for(SectionName.DECISION) == "We will use PostgreSQL."


def test_parse_adr_sections_absent_heading_is_none() -> None:
    markdown = _COMPLETE_ADR.replace("## Context\n\nWe need", "")
    parsed = parse_adr_sections(markdown)
    assert parsed.body_for(SectionName.CONTEXT) is None
