"""ADR aggregate — command-path state and transitions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

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
    AdrInvalidSubmitStatus,
)
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class ADR:
    """ADR lifecycle state for command handlers and event replay.

    Command methods (``create``, ``update_content``, ``update_title``,
    ``submit_for_review``, ``publish``) validate invariants then delegate to
    ``with_*`` transition helpers. Transition helpers take value objects only,
    perform no guards, and are used by command methods and ``rehydrate_adr``.
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
    ) -> ADR:
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

    def update_content(self, content: AdrContent, updated_at: datetime) -> ADR:
        """Replace body content; rejected while ``in_review``."""
        if self.status == AdrStatus.IN_REVIEW:
            raise AdrEditWhileInReview()
        return self.with_content_updated(content, updated_at)

    def update_title(self, title: AdrTitle, updated_at: datetime) -> ADR:
        """Replace title; rejected while ``in_review``."""
        if self.status == AdrStatus.IN_REVIEW:
            raise AdrEditWhileInReview()
        return self.with_title_updated(title, updated_at)

    def submit_for_review(self, updated_at: datetime) -> ADR:
        """Move from ``draft`` to ``in_review``; clears review fields."""
        if self.status != AdrStatus.DRAFT:
            raise AdrInvalidSubmitStatus()
        return self.with_submitted_for_review(updated_at)

    def publish(self, updated_at: datetime) -> ADR:
        """Move from ``after_review`` to ``proposed``; preserves review fields."""
        if self.status != AdrStatus.AFTER_REVIEW:
            raise AdrInvalidPublishStatus()
        return self.with_published(updated_at)

    def with_content_updated(self, content: AdrContent, updated_at: datetime) -> ADR:
        """Transition helper: update content only; review state unchanged."""
        return replace(self, content=content, updated_at=updated_at)

    def with_title_updated(self, title: AdrTitle, updated_at: datetime) -> ADR:
        """Transition helper: update title only; review state unchanged."""
        return replace(self, title=title, updated_at=updated_at)

    def with_submitted_for_review(self, updated_at: datetime) -> ADR:
        """Transition helper: ``in_review`` and cleared review snapshot fields."""
        return replace(
            self,
            status=AdrStatus.IN_REVIEW,
            review_result=None,
            review_error=None,
            reviewed_at=None,
            updated_at=updated_at,
        )

    def with_review_completed(
        self,
        result: ReviewResult,
        reviewed_at: datetime,
    ) -> ADR:
        """Transition helper: ``after_review`` with annotations; clears error."""
        return replace(
            self,
            status=AdrStatus.AFTER_REVIEW,
            review_result=result,
            review_error=None,
            reviewed_at=reviewed_at,
            updated_at=reviewed_at,
        )

    def with_review_failed(self, code: str, message: str) -> ADR:
        """Transition helper: record review failure; status unchanged."""
        return replace(
            self,
            review_result=None,
            review_error=ReviewError(code=code, message=message),
        )

    def with_published(self, updated_at: datetime) -> ADR:
        """Transition helper: ``proposed``; review fields unchanged."""
        return replace(
            self,
            status=AdrStatus.PROPOSED,
            updated_at=updated_at,
        )

    def with_soft_deleted(self) -> ADR:
        """Transition helper: mark deleted; other fields unchanged."""
        return replace(self, is_deleted=True)
