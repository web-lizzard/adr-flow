"""ADR starter template constant tests."""

from domain.adr import ADR_STARTER_TEMPLATE


def test_adr_starter_template_has_five_headings() -> None:
    expected = (
        "## Context\n\n## Options\n\n## Decision\n\n## Status\n\n## Consequences\n"
    )
    assert ADR_STARTER_TEMPLATE == expected
