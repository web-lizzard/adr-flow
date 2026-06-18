"""Rebuild ADR aggregate state from stored domain events."""

from __future__ import annotations

from collections.abc import Sequence

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
from domain.events import DomainEvent


def rehydrate_adr(events: Sequence[DomainEvent]) -> ADR | None:
    """Fold an ordered event stream into an ``ADR``.

    Maps each stored event type to value objects and aggregate transition
    helpers. This module is the only place that pattern-matches event types;
    ``aggregate.py`` does not import event classes.

    Returns ``None`` for an empty stream. Raises ``ValueError`` for unknown
    event types or events that appear before ``ADRCreated``.
    """
    if not events:
        return None

    adr: ADR | None = None
    for event in events:
        match event:
            case ADRCreated():
                adr = ADR.create(
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
                adr = adr.with_content_updated(
                    content=event.content,
                    updated_at=event.occurred_at,
                )
                if event.title is not None:
                    adr = adr.with_title_updated(
                        title=event.title,
                        updated_at=event.occurred_at,
                    )
            case ADRSubmittedForReview():
                if adr is None:
                    msg = "ADRSubmittedForReview before ADRCreated"
                    raise ValueError(msg)
                adr = adr.with_submitted_for_review(updated_at=event.occurred_at)
            case AIReviewCompleted():
                if adr is None:
                    msg = "AIReviewCompleted before ADRCreated"
                    raise ValueError(msg)
                adr = adr.with_review_completed(
                    result=event.review_result,
                    reviewed_at=event.review_result.reviewed_at,
                )
            case AIReviewFailed():
                if adr is None:
                    msg = "AIReviewFailed before ADRCreated"
                    raise ValueError(msg)
                adr = adr.with_review_failed(
                    code=event.code,
                    message=event.message,
                )
            case ADRPublished():
                if adr is None:
                    msg = "ADRPublished before ADRCreated"
                    raise ValueError(msg)
                adr = adr.with_published(updated_at=event.occurred_at)
            case ADRSoftDeleted():
                if adr is None:
                    msg = "ADRSoftDeleted before ADRCreated"
                    raise ValueError(msg)
                adr = adr.with_soft_deleted()
            case _:
                msg = f"Unknown event type: {type(event).__name__}"
                raise ValueError(msg)
    return adr
