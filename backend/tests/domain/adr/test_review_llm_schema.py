"""Review LLM wire schema and mapping tests."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from application.review_quality import validate_review_result
from domain.adr.required_sections import SectionName
from domain.adr.review_llm_schema import (
    CrossSectionReviewPayload,
    ReviewAnnotationPayload,
    ReviewPayload,
    SectionReviewPayload,
    merge_review_results,
    to_review_result,
)
from domain.adr.static_review import synthesize_static_review
from domain.adr.value_objects import ReviewAnnotationKind, SectionRating
from tests.review_quality.cases import ALL_CASES, build_synthetic_result

_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def test_review_payload_accepts_valid_json() -> None:
    payload_json = json.dumps(
        {
            "annotations": [
                {
                    "kind": "inconsistency",
                    "message": "Status may not reflect the decision.",
                    "location": "## Status",
                }
            ]
        }
    )

    payload = ReviewPayload.model_validate_json(payload_json)

    assert len(payload.annotations) == 1
    assert payload.annotations[0].kind == ReviewAnnotationKind.INCONSISTENCY


def test_review_payload_rejects_missing_annotations() -> None:
    with pytest.raises(ValidationError):
        ReviewPayload.model_validate({"notes": "no annotations key"})


def test_review_payload_rejects_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        ReviewAnnotationPayload.model_validate(
            {
                "kind": "unknown_kind",
                "message": "bad",
            }
        )


def test_to_review_result_maps_payload_fields() -> None:
    markdown = "## Context\n\nWe need a store.\n"
    payload = ReviewPayload(
        annotations=(
            ReviewAnnotationPayload(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="Status may not reflect the decision.",
                location="## Status",
            ),
        )
    )

    result = to_review_result(payload, markdown=markdown, reviewed_at=_REVIEWED_AT)

    assert result.reviewed_content == markdown
    assert result.reviewed_at == _REVIEWED_AT
    assert len(result.annotations) == 1
    assert result.annotations[0].kind == ReviewAnnotationKind.INCONSISTENCY
    assert result.annotations[0].location == "## Status"


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda case: case.name)
def test_synthetic_payload_without_section_ratings_fails_validation(
    case,
) -> None:
    expected = build_synthetic_result(case)
    payload = ReviewPayload(
        annotations=tuple(
            ReviewAnnotationPayload(
                kind=annotation.kind,
                message=annotation.message,
                location=annotation.location,
                suggestion=annotation.suggestion,
            )
            for annotation in expected.annotations
        )
    )

    result = to_review_result(
        payload,
        markdown=case.markdown,
        reviewed_at=_REVIEWED_AT,
    )
    validation = validate_review_result(case.markdown, result)

    assert validation.passed is False
    assert any(
        "expected 5 section ratings" in failure for failure in validation.failures
    )


def test_section_review_payload_rejects_score_outside_one_to_five() -> None:
    with pytest.raises(ValidationError):
        SectionReviewPayload(
            section=SectionName.CONTEXT,
            score=0,
            feedback="too low",
        )


def test_section_review_payload_rejects_missing_section_annotations() -> None:
    with pytest.raises(ValidationError):
        SectionReviewPayload(
            section=SectionName.CONTEXT,
            score=3,
            feedback="adequate",
            annotations=(
                ReviewAnnotationPayload(
                    kind=ReviewAnnotationKind.MISSING_SECTION,
                    message="gap",
                    suggestion="add content",
                ),
            ),
        )


def test_merge_review_results_includes_all_five_section_ratings() -> None:
    markdown = "## Context\n\nWe need a store.\n\n## Options\n\nA vs B.\n\n## Decision\n\nPick A.\n\n## Status\n\nAccepted\n\n## Consequences\n\nTradeoffs.\n"
    static_annotations, static_ratings = synthesize_static_review(markdown)
    section_payloads = tuple(
        SectionReviewPayload(
            section=section,
            score=4,
            feedback=f"{section.value} is strong.",
        )
        for section in SectionName
    )
    cross_payload = CrossSectionReviewPayload(annotations=())

    result = merge_review_results(
        static_annotations,
        static_ratings,
        section_payloads,
        cross_payload,
        markdown=markdown,
        reviewed_at=_REVIEWED_AT,
    )

    assert len(result.section_ratings) == 5
    assert {rating.section for rating in result.section_ratings} == set(SectionName)
    assert all(rating.score == 4 for rating in result.section_ratings)


def test_merge_review_results_combines_static_and_llm_annotations() -> None:
    markdown = (  # noqa: E501
        "## Context\n\nWe need a store.\n\n## Options\n\n\n\n## Decision\n\nPick A.\n\n"
        "## Status\n\nAccepted\n\n## Consequences\n\nTradeoffs.\n"
    )
    static_annotations, static_ratings = synthesize_static_review(markdown)
    section_payloads = (
        SectionReviewPayload(
            section=SectionName.CONTEXT,
            score=4,
            feedback="Clear problem.",
        ),
        SectionReviewPayload(
            section=SectionName.DECISION,
            score=3,
            feedback="Specific enough.",
        ),
        SectionReviewPayload(
            section=SectionName.STATUS,
            score=4,
            feedback="Consistent.",
        ),
        SectionReviewPayload(
            section=SectionName.CONSEQUENCES,
            score=3,
            feedback="Balanced.",
        ),
    )
    cross_payload = CrossSectionReviewPayload(
        annotations=(
            ReviewAnnotationPayload(
                kind=ReviewAnnotationKind.INCONSISTENCY,
                message="Status may not reflect the decision.",
                location="## Status",
            ),
        )
    )

    result = merge_review_results(
        static_annotations,
        static_ratings,
        section_payloads,
        cross_payload,
        markdown=markdown,
        reviewed_at=_REVIEWED_AT,
    )

    assert any(
        annotation.kind == ReviewAnnotationKind.MISSING_SECTION
        for annotation in result.annotations
    )
    assert any(
        annotation.kind == ReviewAnnotationKind.INCONSISTENCY
        for annotation in result.annotations
    )
    options_rating = next(
        rating
        for rating in result.section_ratings
        if rating.section == SectionName.OPTIONS
    )
    assert options_rating.score == 0
    assert isinstance(options_rating, SectionRating)
