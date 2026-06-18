"""Domain-owned review instructions for ADR AI review."""

from domain.adr.required_sections import REQUIRED_SECTION_HEADINGS, SectionName
from domain.adr.review_actionability import format_actionability_requirements_for_prompt

_PLACEHOLDER_TOKENS = ("tbd", "todo", "n/a")


def build_review_system_prompt() -> str:
    """Build the system prompt for ADR review with domain section and quality rules."""
    section_list = ", ".join(section.value for section in SectionName)
    placeholder_list = ", ".join(_PLACEHOLDER_TOKENS)

    return (
        "You review Architecture Decision Records (ADRs). "
        "Return JSON with an annotations array.\n\n"
        f"Required sections (exact ## headings): {', '.join(REQUIRED_SECTION_HEADINGS)}. "
        f"Section names: {section_list}.\n\n"
        "Missing or empty section rules:\n"
        f"- Treat a section as missing when its heading is absent, the body is empty, "
        f"or the body is only a placeholder ({placeholder_list}, case-insensitive).\n"
        "- Emit exactly one missing_section annotation per gap. "
        "Reference the section in location (e.g. ## Context) and provide an actionable suggestion.\n\n"
        "Inconsistency rules:\n"
        "- When both Decision and Status sections have substantive content, check whether "
        "Status reflects the recorded Decision; flag contradictions with a section-scoped "
        "location (e.g. ## Status).\n\n"
        "Conciseness rules:\n"
        "- Flag overly verbose ADR bodies (especially long Context sections); cite the "
        "relevant section in location and suggest what to trim.\n\n"
        f"{format_actionability_requirements_for_prompt()}"
    )


def build_review_user_message(markdown: str) -> str:
    """Wrap ADR markdown for the user role in a review completion request."""
    return (
        "Review the following ADR markdown and return annotations as specified:\n\n"
        f"{markdown}"
    )
