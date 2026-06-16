"""Harness input/output contracts for fixture-driven review grading."""

from dataclasses import dataclass


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
