"""ADR aggregate — command-path state and transitions."""

from collections.abc import Sequence

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Self

from domain.adr.events import (
    ADRContentUpdated,
    ADRCreated,
    ADRPublished,
    ADRSoftDeleted,
    ADRSubmittedForReview,
    AIReviewCompleted,
    AIReviewFailed,
)
from domain.adr.value_objects import (
    AdrContent,
    AdrId,
    AdrStatus,
    AdrTitle,
    ReviewError,
    ReviewResult,
)
from domain.errors import (
    AdrEditWhileInReview,
    AdrInvalidPublishStatus,
    AdrInvalidReviewStatus,
    AdrInvalidSubmitStatus,
)
from domain.events import DomainEvent
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class ADR:
    """ADR lifecycle state for command handlers and event replay.

    Command methods validate invariants then delegate to private ``_with_*``
    transition helpers. ``restore`` folds stored domain events for load paths.
    """

    adr_id: AdrId
    user_id: UserId
    title: AdrTitle
    content: AdrContent
    status: AdrStatus
    review_result: ReviewResult | None
    review_error: ReviewError | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        adr_id: AdrId,
        user_id: UserId,
        title: AdrTitle,
        content: AdrContent,
        created_at: datetime,
    ) -> Self:
        """Bootstrap a new ADR in ``draft`` (no prior event stream)."""
        return cls(
            adr_id=adr_id,
            user_id=user_id,
            title=title,
            content=content,
            status=AdrStatus.DRAFT,
            review_result=None,
            review_error=None,
            is_deleted=False,
            created_at=created_at,
            updated_at=created_at,
            reviewed_at=None,
        )

    @classmethod
    def restore(cls, events: Sequence[DomainEvent]) -> Self | None:
        """Fold an ordered event stream into aggregate state.

        Returns ``None`` for an empty stream. Raises ``ValueError`` for unknown
        event types or events that appear before ``ADRCreated``.
        """
        if not events:
            return None

        adr: ADR | None = None
        for event in events:
            match event:
                case ADRCreated():
                    adr = cls.create(
                        adr_id=event.adr_id,
                        user_id=event.user_id,
                        title=event.title,
                        content=event.content,
                        created_at=event.occurred_at,
                    )
                case ADRContentUpdated():
                    if adr is None:
                        msg = "ADRContentUpdated before ADRCreated"
                        raise ValueError(msg)
                    adr = adr._with_content_updated(
                        content=event.content,
                        updated_at=event.occurred_at,
                    )
                    if event.title is not None:
                        adr = adr._with_title_updated(
                            title=event.title,
                            updated_at=event.occurred_at,
                        )
                case ADRSubmittedForReview():
                    if adr is None:
                        msg = "ADRSubmittedForReview before ADRCreated"
                        raise ValueError(msg)
                    adr = adr._with_submitted_for_review(updated_at=event.occurred_at)
                case AIReviewCompleted():
                    if adr is None:
                        msg = "AIReviewCompleted before ADRCreated"
                        raise ValueError(msg)
                    adr = adr._with_review_completed(
                        result=event.review_result,
                        reviewed_at=event.review_result.reviewed_at,
                    )
                case AIReviewFailed():
                    if adr is None:
                        msg = "AIReviewFailed before ADRCreated"
                        raise ValueError(msg)
                    adr = adr._with_review_failed(
                        code=event.code,
                        message=event.message,
                    )
                case ADRPublished():
                    if adr is None:
                        msg = "ADRPublished before ADRCreated"
                        raise ValueError(msg)
                    adr = adr._with_published(updated_at=event.occurred_at)
                case ADRSoftDeleted():
                    if adr is None:
                        msg = "ADRSoftDeleted before ADRCreated"
                        raise ValueError(msg)
                    adr = adr._with_soft_deleted()
                case _:
                    msg = f"Unknown event type: {type(event).__name__}"
                    raise ValueError(msg)
        return adr

    def update_content(self, content: AdrContent, updated_at: datetime) -> Self:
        """Replace body content; rejected while ``in_review``."""
        if self.status == AdrStatus.IN_REVIEW:
            raise AdrEditWhileInReview()
        return self._with_content_updated(content, updated_at)

    def update_title(self, title: AdrTitle, updated_at: datetime) -> Self:
        """Replace title; rejected while ``in_review``."""
        if self.status == AdrStatus.IN_REVIEW:
            raise AdrEditWhileInReview()
        return self._with_title_updated(title, updated_at)

    def submit_for_review(self, updated_at: datetime) -> Self:
        """Move from ``draft`` to ``in_review``; clears review fields."""
        if self.status != AdrStatus.DRAFT:
            raise AdrInvalidSubmitStatus()
        return self._with_submitted_for_review(updated_at)

    def publish(self, updated_at: datetime) -> Self:
        """Move from ``after_review`` to ``proposed``; preserves review fields."""
        if self.status != AdrStatus.AFTER_REVIEW:
            raise AdrInvalidPublishStatus()
        return self._with_published(updated_at)

    def complete_review(self, result: ReviewResult, reviewed_at: datetime) -> Self:
        """Record successful AI review; requires ``in_review``."""
        if self.status != AdrStatus.IN_REVIEW:
            raise AdrInvalidReviewStatus()
        return self._with_review_completed(result=result, reviewed_at=reviewed_at)

    def fail_review(self, code: str, message: str) -> Self:
        """Record failed AI review; requires ``in_review``."""
        if self.status != AdrStatus.IN_REVIEW:
            raise AdrInvalidReviewStatus()
        return self._with_review_failed(code=code, message=message)

    def _with_content_updated(self, content: AdrContent, updated_at: datetime) -> Self:
        return replace(self, content=content, updated_at=updated_at)

    def _with_title_updated(self, title: AdrTitle, updated_at: datetime) -> Self:
        return replace(self, title=title, updated_at=updated_at)

    def _with_submitted_for_review(self, updated_at: datetime) -> Self:
        return replace(
            self,
            status=AdrStatus.IN_REVIEW,
            review_result=None,
            review_error=None,
            reviewed_at=None,
            updated_at=updated_at,
        )

    def _with_review_completed(
        self, result: ReviewResult, reviewed_at: datetime
    ) -> Self:
        return replace(
            self,
            status=AdrStatus.AFTER_REVIEW,
            review_result=result,
            review_error=None,
            reviewed_at=reviewed_at,
            updated_at=reviewed_at,
        )

    def _with_review_failed(self, code: str, message: str) -> Self:
        return replace(
            self,
            review_result=None,
            review_error=ReviewError(code=code, message=message),
        )

    def _with_published(self, updated_at: datetime) -> Self:
        return replace(
            self,
            status=AdrStatus.PROPOSED,
            updated_at=updated_at,
        )

    def _with_soft_deleted(self) -> Self:
        return replace(self, is_deleted=True)
