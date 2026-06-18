"""Test helpers for ADR domain aggregates."""

from datetime import UTC, datetime
from uuid import UUID

from domain.adr import ADR, AdrContent, AdrId, AdrStatus, AdrTitle
from domain.user import UserId


def draft_adr(
    *,
    adr_id: UUID,
    user_id: UUID,
    title: str,
    content: str = "## Context",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> ADR:
    created = created_at or datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
    updated = updated_at or created
    return ADR(
        adr_id=AdrId(adr_id),
        user_id=UserId(user_id),
        title=AdrTitle(title),
        content=AdrContent(content),
        status=AdrStatus.DRAFT,
        review_result=None,
        review_error=None,
        is_deleted=False,
        created_at=created,
        updated_at=updated,
    )
