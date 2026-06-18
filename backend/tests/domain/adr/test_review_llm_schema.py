"""Review LLM wire schema and mapping tests."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from application.review_quality import validate_review_result
from domain.adr.review_llm_schema import (
    ReviewAnnotationPayload,
    ReviewPayload,
    to_review_result,
)
from domain.adr.value_objects import ReviewAnnotationKind
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
def test_synthetic_payload_round_trips_through_validate_review_result(
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

    assert validation.passed is True, validation.failures
