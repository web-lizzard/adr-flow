"""Port for ADR AI review orchestration."""

from typing import Protocol

from domain.adr.value_objects import ReviewResult


class AdrReviewPort(Protocol):
    async def review_adr(
        self,
        markdown: str,
        *,
        validation_feedback: tuple[str, ...] = (),
    ) -> ReviewResult: ...
