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
    PLACEHOLDER_TOKENS,
    REQUIRED_SECTION_HEADINGS,
    ParsedAdrSections,
    SectionName,
    find_missing_or_empty_sections,
    parse_adr_sections,
)
from domain.adr.review_instructions import (
    build_cross_section_system_prompt,
    build_review_system_prompt,
    build_review_user_message,
    build_section_system_prompt,
    build_section_user_message,
)
from domain.adr.review_llm_schema import (
    CrossSectionReviewPayload,
    ReviewAnnotationPayload,
    ReviewPayload,
    SectionReviewPayload,
    merge_review_results,
    to_review_result,
)
from domain.adr.static_review import synthesize_static_review
from domain.adr.template import ADR_STARTER_TEMPLATE
from domain.adr.value_objects import (
    AdrContent,
    AdrId,
    AdrStatus,
    AdrTitle,
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewError,
    ReviewResult,
    SectionRating,
)

__all__ = [
    "ADR_STARTER_TEMPLATE",
    "PLACEHOLDER_TOKENS",
    "REQUIRED_SECTION_HEADINGS",
    "ParsedAdrSections",
    "SectionName",
    "find_missing_or_empty_sections",
    "parse_adr_sections",
    "build_cross_section_system_prompt",
    "build_review_system_prompt",
    "build_review_user_message",
    "build_section_system_prompt",
    "build_section_user_message",
    "CrossSectionReviewPayload",
    "ReviewAnnotationPayload",
    "ReviewPayload",
    "SectionReviewPayload",
    "merge_review_results",
    "to_review_result",
    "synthesize_static_review",
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
    "ReviewError",
    "ReviewResult",
    "SectionRating",
]
