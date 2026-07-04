"""Domain-owned review instructions for ADR AI review."""

from domain.adr.required_sections import (
    PLACEHOLDER_TOKENS,
    REQUIRED_SECTION_HEADINGS,
    SectionName,
)
from domain.adr.review_actionability import format_actionability_requirements_for_prompt
from domain.adr.value_objects import ReviewAnnotationKind

_UNIVERSAL_RUBRIC = """\
Universal score anchors (assign scores 1–5 only; score 0 is pre-computed for gaps):
- Score 1: Off-topic or wrong role for this section.
- Score 2: Topic-adjacent but insufficient (vague, tribal knowledge).
- Score 3: Adequate draft — intent clear but lacks specificity or tradeoffs.
- Score 4: Strong — meets ADR conventions; only minor improvements possible.
- Score 5: Exemplary — concise and complete for the decision's stakes.
"""

_SECTION_RUBRICS: dict[SectionName, str] = {
    SectionName.CONTEXT: """\
Context section criteria (value-neutral problem statement, not the solution):
- Score 1: Unrelated content or solution-pitch dominates.
- Score 2: Problem implied but unclear; undefined acronyms; no trigger.
- Score 3: Problem understandable but missing constraints, scope, or forces.
- Score 4: Clear problem, current state, constraints, and scope.
- Score 5: Quantified drivers, links to prior ADRs/issues, explicit forces in tension.
Score cap: solution language in Context → max 2.""",
    SectionName.OPTIONS: """\
Options section criteria (genuine alternatives with tradeoffs):
- Score 1: Unrelated technologies or Decision restated as the only path.
- Score 2: Only one substantive option or straw-man alternatives.
- Score 3: Multiple options named but thin comparison or missing rejection rationale.
- Score 4: ≥2 genuine alternatives with real pros and cons.
- Score 5: MECE drivers and explicit tradeoff prioritization.
Score cap: only one option listed → max 2.""",
    SectionName.DECISION: """\
Decision section criteria (active-voice commitment):
- Score 1: Hedging without commitment or contradicts Context/Options.
- Score 2: Direction named but not actionable (no technology/version/scope).
- Score 3: Specific choice but missing bounded scope or success criteria.
- Score 4: Active voice, named approach, clear scope, implementable.
- Score 5: Fully implementable with explicit non-goals.
Score cap: passive voice only → max 3; no specific approach → max 2.""",
    SectionName.STATUS: """\
Status section criteria (lifecycle state aligned with Decision):
- Score 1: Unrelated value or contradicts Decision.
- Score 2: Valid lifecycle word but ambiguous or generic.
- Score 3: Reflects state at high level but commitment unclear.
- Score 4: Clear standard status consistent with Decision.
- Score 5: Includes validity period, review trigger, or supersession link.
Score cap: contradicts Decision → max 1.""",
    SectionName.CONSEQUENCES: """\
Consequences section criteria (positive, negative, and neutral outcomes):
- Score 1: Unrelated outcomes or aspirational fluff.
- Score 2: Only positives or vague negatives.
- Score 3: Mix of positive/negative but shallow operational impact.
- Score 4: Balanced with ≥2 substantive positives and ≥2 negatives/tradeoffs.
- Score 5: Quantified impacts and follow-up tasks identified.
Score cap: only positives listed → max 2.""",
}


def build_section_system_prompt(section: SectionName) -> str:
    """Build a section-scoped system prompt with rubric and rating contract."""
    return (
        f"You rate the ADR {section.value} section (heading ## {section.value}). "
        "Return JSON with section, score (1–5), feedback, and optional annotations.\n\n"
        "Do not detect or annotate missing sections — gaps are detected before your call.\n\n"
        f"{_UNIVERSAL_RUBRIC}\n"
        f"{_SECTION_RUBRICS[section]}\n\n"
        "Cite specific phrases from the section body in feedback.\n"
        f"{format_actionability_requirements_for_prompt(kinds=(ReviewAnnotationKind.CONCISENESS,))}"
    )


def build_cross_section_system_prompt() -> str:
    """Build the system prompt for Decision↔Status inconsistency checks."""
    return (
        "You review Architecture Decision Records for cross-section consistency. "
        "Return JSON with an annotations array only.\n\n"
        "Check whether Status reflects the recorded Decision when both sections "
        "have substantive content. Flag contradictions with inconsistency "
        "annotations and section-scoped location (e.g. ## Status).\n\n"
        "Do not detect or annotate missing sections — gaps are detected before your call.\n\n"
        f"{format_actionability_requirements_for_prompt(kinds=(ReviewAnnotationKind.INCONSISTENCY,))}"
    )


def build_section_user_message(
    section: SectionName,
    body: str,
    *,
    doc_markdown: str | None = None,
) -> str:
    """Wrap a section body for the user role in a section rating request."""
    parts = [
        f"Rate the following {section.value} section and return JSON as specified:",
        "",
        body,
    ]
    if section is SectionName.CONTEXT and doc_markdown is not None:
        parts.extend(
            [
                "",
                "Full ADR markdown (for conciseness/length context):",
                doc_markdown,
                "",
                "Flag conciseness in annotations if the overall document or Context "
                "is overly verbose; suggest what to trim.",
            ]
        )
    return "\n".join(parts)


def build_review_system_prompt() -> str:
    """Build the legacy monolithic system prompt (superseded by section-scoped prompts)."""
    section_list = ", ".join(section.value for section in SectionName)
    placeholder_list = ", ".join(PLACEHOLDER_TOKENS)

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


def build_review_user_message(
    markdown: str,
    *,
    validation_feedback: tuple[str, ...] = (),
) -> str:
    """Wrap ADR markdown for the user role in a review completion request."""
    parts = [
        "Review the following ADR markdown and return annotations as specified:",
    ]
    if validation_feedback:
        parts.extend(
            [
                "",
                "Your previous output failed static validation. Fix these issues:",
                *(f"- {failure}" for failure in validation_feedback),
            ]
        )
    parts.extend(["", markdown])
    return "\n".join(parts)
