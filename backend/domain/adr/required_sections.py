"""Required ADR section parsing and gap detection."""

from dataclasses import dataclass
from enum import StrEnum

REQUIRED_SECTION_HEADINGS: tuple[str, ...] = (
    "## Context",
    "## Options",
    "## Decision",
    "## Status",
    "## Consequences",
)


class SectionName(StrEnum):
    CONTEXT = "Context"
    OPTIONS = "Options"
    DECISION = "Decision"
    STATUS = "Status"
    CONSEQUENCES = "Consequences"


_HEADING_TO_SECTION: dict[str, SectionName] = {
    heading: SectionName(heading.removeprefix("## "))
    for heading in REQUIRED_SECTION_HEADINGS
}

_PLACEHOLDER_TOKENS = frozenset({"tbd", "todo", "n/a"})


@dataclass(frozen=True, slots=True)
class ParsedAdrSections:
    context: str | None
    options: str | None
    decision: str | None
    status: str | None
    consequences: str | None

    def body_for(self, section: SectionName) -> str | None:
        return {
            SectionName.CONTEXT: self.context,
            SectionName.OPTIONS: self.options,
            SectionName.DECISION: self.decision,
            SectionName.STATUS: self.status,
            SectionName.CONSEQUENCES: self.consequences,
        }[section]


def parse_adr_sections(markdown: str) -> ParsedAdrSections:
    bodies: dict[SectionName, str | None] = dict.fromkeys(SectionName, None)
    current_section: SectionName | None = None
    current_body_lines: list[str] = []

    def flush() -> None:
        nonlocal current_section, current_body_lines
        if current_section is not None:
            bodies[current_section] = "\n".join(current_body_lines).strip()
        current_body_lines = []

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            current_section = _HEADING_TO_SECTION.get(line.rstrip())
        elif current_section is not None:
            current_body_lines.append(line)

    flush()

    return ParsedAdrSections(
        context=bodies[SectionName.CONTEXT],
        options=bodies[SectionName.OPTIONS],
        decision=bodies[SectionName.DECISION],
        status=bodies[SectionName.STATUS],
        consequences=bodies[SectionName.CONSEQUENCES],
    )


def find_missing_or_empty_sections(markdown: str) -> frozenset[SectionName]:
    parsed = parse_adr_sections(markdown)
    missing: set[SectionName] = set()
    for section in SectionName:
        body = parsed.body_for(section)
        if body is None or not body.strip() or _is_placeholder_only(body):
            missing.add(section)
    return frozenset(missing)


def _is_placeholder_only(text: str) -> bool:
    return text.strip().lower() in _PLACEHOLDER_TOKENS
