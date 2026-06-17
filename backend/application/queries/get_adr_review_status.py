from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from application.ports.adr_repository import AdrRepository
from application.review_metadata import ReviewErrorMetadata
from domain.adr.value_objects import ReviewResult
from domain.errors import AdrNotFound


@dataclass(frozen=True, slots=True)
class GetAdrReviewStatusQuery:
    adr_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class AdrReviewStatus:
    status: str
    reviewed_at: datetime | None
    review_error: ReviewErrorMetadata | None
    annotation_counts: dict[str, int] | None


class GetAdrReviewStatusQueryHandler:
    def __init__(self, adr_repository: AdrRepository) -> None:
        self._adr_repository = adr_repository

    async def handle(self, query: GetAdrReviewStatusQuery) -> AdrReviewStatus:
        adr = await self._adr_repository.find_by_id_for_owner(
            query.adr_id,
            query.user_id,
        )
        if adr is None:
            raise AdrNotFound()

        return AdrReviewStatus(
            status=adr.status,
            reviewed_at=adr.reviewed_at,
            review_error=adr.review_error,
            annotation_counts=_annotation_counts(adr.review_annotations),
        )


def _annotation_counts(review_result: ReviewResult | None) -> dict[str, int] | None:
    if review_result is None:
        return None
    counts: dict[str, int] = {}
    for annotation in review_result.annotations:
        kind = annotation.kind.value
        counts[kind] = counts.get(kind, 0) + 1
    return counts
