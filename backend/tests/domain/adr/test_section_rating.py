"""SectionRating value object validation tests."""

import pytest
from pydantic import ValidationError

from domain.adr.required_sections import SectionName
from domain.adr.value_objects import SectionRating


def test_section_rating_accepts_valid_score_with_feedback() -> None:
    rating = SectionRating(
        section=SectionName.CONTEXT,
        score=4,
        feedback="Problem and constraints are clear.",
    )

    assert rating.section == SectionName.CONTEXT
    assert rating.score == 4
    assert rating.feedback == "Problem and constraints are clear."


def test_section_rating_accepts_score_zero_without_feedback() -> None:
    rating = SectionRating(section=SectionName.DECISION, score=0, feedback="")

    assert rating.score == 0
    assert rating.feedback == ""


@pytest.mark.parametrize("invalid_score", [-1, 6, 10])
def test_section_rating_rejects_out_of_range_scores(invalid_score: int) -> None:
    with pytest.raises(ValidationError):
        SectionRating(
            section=SectionName.CONTEXT,
            score=invalid_score,
            feedback="ok",
        )


@pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
def test_section_rating_requires_non_empty_feedback_for_scores_at_least_one(
    score: int,
) -> None:
    with pytest.raises(ValidationError):
        SectionRating(section=SectionName.OPTIONS, score=score, feedback="")

    with pytest.raises(ValidationError):
        SectionRating(section=SectionName.OPTIONS, score=score, feedback="   ")


def test_review_result_defaults_section_ratings_to_empty_tuple() -> None:
    from datetime import UTC, datetime

    from domain.adr.value_objects import ReviewResult

    result = ReviewResult(
        annotations=(),
        reviewed_at=datetime(2026, 7, 4, tzinfo=UTC),
    )

    assert result.section_ratings == ()
