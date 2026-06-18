"""ADR aggregate vocabulary."""

from domain.adr.aggregate import ADR
from domain.adr.events import (
    ADRContentUpdated,
    ADRCreated,
    ADRPublished,
    ADRSoftDeleted,
    ADRSubmittedForReview,
    AIReviewCompleted,
    AIReviewFailed,
)
from domain.adr.required_sections import (
    REQUIRED_SECTION_HEADINGS,
    SectionName,
    find_missing_or_empty_sections,
    parse_adr_sections,
)
from domain.adr.review_instructions import (
    build_review_system_prompt,
    build_review_user_message,
)
from domain.adr.review_llm_schema import (
    ReviewAnnotationPayload,
    ReviewPayload,
    to_review_result,
)
from domain.adr.template import ADR_STARTER_TEMPLATE
from domain.adr.value_objects import (
    AdrContent,
    AdrId,
    AdrStatus,
    AdrTitle,
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)

__all__ = [
    "ADR_STARTER_TEMPLATE",
    "REQUIRED_SECTION_HEADINGS",
    "SectionName",
    "find_missing_or_empty_sections",
    "parse_adr_sections",
    "build_review_system_prompt",
    "build_review_user_message",
    "ReviewAnnotationPayload",
    "ReviewPayload",
    "to_review_result",
    "ADR",
    "ADRContentUpdated",
    "ADRCreated",
    "ADRPublished",
    "ADRSoftDeleted",
    "ADRSubmittedForReview",
    "AIReviewCompleted",
    "AIReviewFailed",
    "AdrContent",
    "AdrId",
    "AdrStatus",
    "AdrTitle",
    "ReviewAnnotation",
    "ReviewAnnotationKind",
    "ReviewResult",
]
