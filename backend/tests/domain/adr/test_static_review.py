"""Static Phase 0 gap synthesis tests."""

import pytest

from domain.adr.required_sections import SectionName
from domain.adr.static_review import synthesize_static_review
from domain.adr.value_objects import ReviewAnnotationKind
from tests.review_quality.cases import ALL_CASES, load_fixture


def test_complete_adr_produces_no_static_output() -> None:
    markdown = load_fixture("complete.md")

    annotations, ratings = synthesize_static_review(markdown)

    assert annotations == ()
    assert ratings == ()


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda case: case.name)
def test_incomplete_fixtures_emit_gap_annotations_and_score_zero_ratings(
    case,
) -> None:
    if not case.expected_missing_sections:
        return

    annotations, ratings = synthesize_static_review(case.markdown)

    assert len(annotations) == len(case.expected_missing_sections)
    assert {annotation.location for annotation in annotations} == {
        f"## {section}" for section in case.expected_missing_sections
    }
    for annotation in annotations:
        assert annotation.kind == ReviewAnnotationKind.MISSING_SECTION
        assert annotation.message
        assert annotation.suggestion

    rated_sections = {rating.section for rating in ratings}
    assert rated_sections == {
        SectionName(section) for section in case.expected_missing_sections
    }
    for rating in ratings:
        assert rating.score == 0


def test_each_gap_section_emits_exactly_one_annotation() -> None:
    markdown = load_fixture("missing_multiple_sections.md")

    annotations, _ = synthesize_static_review(markdown)

    locations = [annotation.location for annotation in annotations]
    assert len(locations) == len(set(locations))
