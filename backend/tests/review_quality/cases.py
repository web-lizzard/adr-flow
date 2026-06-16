"""Harness input/output contracts for fixture-driven review grading."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ReviewQualityCase:
    name: str
    markdown: str
    expected_missing_sections: frozenset[str]


@dataclass(frozen=True, slots=True)
class ReviewQualityVerdict:
    passed: bool
    missing_section_precision: float
    missing_section_recall: float
    failures: tuple[str, ...]


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def build_synthetic_result(case: ReviewQualityCase) -> ReviewResult:
    annotations = tuple(
        ReviewAnnotation(
            kind=ReviewAnnotationKind.MISSING_SECTION,
            message=f"Missing {section} section",
            location=f"## {section}",
            suggestion=f"Add substantive content for the {section} section.",
        )
        for section in sorted(case.expected_missing_sections)
    )
    return ReviewResult(annotations=annotations, reviewed_at=_REVIEWED_AT)


ALL_CASES: tuple[ReviewQualityCase, ...] = (
    ReviewQualityCase(
        name="complete",
        markdown=load_fixture("complete.md"),
        expected_missing_sections=frozenset(),
    ),
    ReviewQualityCase(
        name="missing_context",
        markdown=load_fixture("missing_context.md"),
        expected_missing_sections=frozenset({"Context"}),
    ),
    ReviewQualityCase(
        name="empty_decision",
        markdown=load_fixture("empty_decision.md"),
        expected_missing_sections=frozenset({"Decision"}),
    ),
    ReviewQualityCase(
        name="placeholder_status",
        markdown=load_fixture("placeholder_status.md"),
        expected_missing_sections=frozenset({"Status"}),
    ),
    ReviewQualityCase(
        name="missing_multiple_sections",
        markdown=load_fixture("missing_multiple_sections.md"),
        expected_missing_sections=frozenset({"Options", "Decision", "Consequences"}),
    ),
    ReviewQualityCase(
        name="wrong_heading_alternatives",
        markdown=load_fixture("wrong_heading_alternatives.md"),
        expected_missing_sections=frozenset({"Options"}),
    ),
    ReviewQualityCase(
        name="extra_sections",
        markdown=load_fixture("extra_sections.md"),
        expected_missing_sections=frozenset(),
    ),
)
