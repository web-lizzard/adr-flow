"""RunAiReview event handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from application.handlers.run_ai_review import RunAiReviewHandler
from application.ports.event_store import StoredEvent
from domain.adr import (
    ADRSubmittedForReview,
    AIReviewCompleted,
    AIReviewFailed,
    AdrContent,
    AdrId,
)
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from domain.user.value_objects import UserId
from tests.application.commands.fakes import (
    FakeEventStore,
    FakeUnitOfWorkFactory,
    after_review_stream,
    in_review_stream,
    stream_with_review_failure,
)

_REVIEWED_AT = datetime(2026, 6, 17, 12, 0, tzinfo=UTC)


class FakeAdrReviewService:
    def __init__(self, *, results: list[ReviewResult] | None = None) -> None:
        self._results = list(results or [])
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def review_adr(
        self,
        markdown: str,
        *,
        validation_feedback: tuple[str, ...] = (),
    ) -> ReviewResult:
        self.calls.append((markdown, validation_feedback))
        if not self._results:
            msg = "No fake review results configured"
            raise RuntimeError(msg)
        return self._results.pop(0)


def _valid_result(markdown: str) -> ReviewResult:
    return ReviewResult(
        annotations=(
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Decision section",
                location="## Decision",
                suggestion="Document the chosen option.",
            ),
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Status section",
                location="## Status",
                suggestion="Record the current status.",
            ),
            ReviewAnnotation(
                kind=ReviewAnnotationKind.MISSING_SECTION,
                message="Missing Consequences section",
                location="## Consequences",
                suggestion="Describe trade-offs.",
            ),
        ),
        reviewed_at=_REVIEWED_AT,
        reviewed_content=markdown,
    )


def _stored_submitted_event(
    *,
    adr_id: UUID,
    user_id: UUID,
    content: str,
    event_id: UUID | None = None,
) -> StoredEvent:
    occurred_at = datetime(2026, 6, 17, 11, 0, tzinfo=UTC)
    event = ADRSubmittedForReview(
        adr_id=AdrId(adr_id),
        user_id=UserId(user_id),
        content=AdrContent(content),
        occurred_at=occurred_at,
    )
    return StoredEvent(
        id=event_id or uuid4(),
        aggregate_type="adr",
        aggregate_id=adr_id,
        event=event,
        occurred_at=occurred_at,
    )


def test_run_ai_review_applies_valid_result_and_marks_event_processed() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nWe need a store.\n\n## Options\n\nA or B.\n"
    event_id = uuid4()
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content, event_id=event_id
    )
    event_store = FakeEventStore(
        streams={
            (adr_id, "adr"): in_review_stream(
                adr_id=adr_id,
                user_id=user_id,
                content=content,
                submit_event_id=event_id,
            )
        }
    )
    review_service = FakeAdrReviewService(results=[_valid_result(content)])
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = RunAiReviewHandler(uow_factory, review_service)

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == [(content, ())]
    assert event_store.load_stream_calls == [(adr_id, "adr"), (adr_id, "adr")]
    persist_uow = uow_factory.unit_of_works[1]
    assert persist_uow.locked_aggregates == [adr_id]
    events, aggregate_id, aggregate_type = persist_uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    assert len(events) == 1
    assert isinstance(events[0], AIReviewCompleted)

    applied_id, applied_result, _ = persist_uow.adr_projection.applied_results[0]
    assert applied_id == adr_id
    assert applied_result.reviewed_content == content
    processed_ids = [
        processed_id for processed_id, _ in persist_uow.event_store.marked_processed
    ]
    assert stored_event.id in processed_ids
    assert len(processed_ids) == 2


def test_run_ai_review_retries_once_on_invalid_output_then_succeeds() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nWe need a store.\n\n## Options\n\nA or B.\n"
    event_id = uuid4()
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content, event_id=event_id
    )
    event_store = FakeEventStore(
        streams={
            (adr_id, "adr"): in_review_stream(
                adr_id=adr_id,
                user_id=user_id,
                content=content,
                submit_event_id=event_id,
            )
        }
    )
    invalid = ReviewResult(annotations=(), reviewed_at=_REVIEWED_AT)
    valid = _valid_result(content)
    review_service = FakeAdrReviewService(results=[invalid, valid])
    handler = RunAiReviewHandler(
        FakeUnitOfWorkFactory(event_store=event_store), review_service
    )

    asyncio.run(handler.handle(stored_event))

    assert len(review_service.calls) == 2
    assert review_service.calls[0][1] == ()
    assert review_service.calls[1][1] != ()


def test_run_ai_review_records_terminal_failure_after_retry_exhausted() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nWe need a store.\n\n## Options\n\nA or B.\n"
    event_id = uuid4()
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content, event_id=event_id
    )
    event_store = FakeEventStore(
        streams={
            (adr_id, "adr"): in_review_stream(
                adr_id=adr_id,
                user_id=user_id,
                content=content,
                submit_event_id=event_id,
            )
        }
    )
    invalid = ReviewResult(annotations=(), reviewed_at=_REVIEWED_AT)
    review_service = FakeAdrReviewService(results=[invalid, invalid])
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = RunAiReviewHandler(uow_factory, review_service)

    asyncio.run(handler.handle(stored_event))

    persist_uow = uow_factory.unit_of_works[1]
    assert persist_uow.locked_aggregates == [adr_id]
    events, _, _ = persist_uow.event_store.appended[0]
    assert isinstance(events[0], AIReviewFailed)
    assert events[0].source_event_id == event_id

    _, review_error, _ = persist_uow.adr_projection.recorded_failures[0]
    assert review_error.source_event_id == event_id
    assert review_error.code == "validation_failed"
    processed_ids = [
        processed_id for processed_id, _ in persist_uow.event_store.marked_processed
    ]
    assert event_id in processed_ids
    assert len(processed_ids) == 2


def test_run_ai_review_is_idempotent_when_adr_already_after_review() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nDone"
    event_id = uuid4()
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content, event_id=event_id
    )
    review_result = ReviewResult(annotations=(), reviewed_at=_REVIEWED_AT)
    event_store = FakeEventStore(
        streams={
            (adr_id, "adr"): after_review_stream(
                adr_id=adr_id,
                user_id=user_id,
                content=content,
                review_result=review_result,
                submit_event_id=event_id,
            )
        }
    )
    review_service = FakeAdrReviewService()
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = RunAiReviewHandler(uow_factory, review_service)

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == []
    assert len(uow_factory.unit_of_works) == 1
    skip_uow = uow_factory.unit_of_works[0]
    assert skip_uow.event_store.appended == []
    assert skip_uow.event_store.marked_processed[0][0] == stored_event.id


def test_run_ai_review_skips_when_failure_already_recorded_for_event() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nDone"
    event_id = uuid4()
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content, event_id=event_id
    )
    event_store = FakeEventStore(
        streams={
            (adr_id, "adr"): stream_with_review_failure(
                adr_id=adr_id,
                user_id=user_id,
                content=content,
                source_event_id=event_id,
            )
        }
    )
    review_service = FakeAdrReviewService()
    handler = RunAiReviewHandler(
        FakeUnitOfWorkFactory(event_store=event_store), review_service
    )

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == []


def test_run_ai_review_skips_when_stream_empty() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nDone"
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content
    )
    event_store = FakeEventStore(streams={(adr_id, "adr"): []})
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    review_service = FakeAdrReviewService()
    handler = RunAiReviewHandler(uow_factory, review_service)

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == []
    assert uow_factory.unit_of_works[0].event_store.marked_processed[0][0] == (
        stored_event.id
    )


def test_run_ai_review_skips_on_ownership_mismatch() -> None:
    adr_id = uuid4()
    owner_id = uuid4()
    other_user_id = uuid4()
    content = "## Context\n\nDone"
    event_id = uuid4()
    stored_event = _stored_submitted_event(
        adr_id=adr_id,
        user_id=other_user_id,
        content=content,
        event_id=event_id,
    )
    event_store = FakeEventStore(
        streams={
            (adr_id, "adr"): in_review_stream(
                adr_id=adr_id,
                user_id=owner_id,
                content=content,
                submit_event_id=event_id,
            )
        }
    )
    review_service = FakeAdrReviewService()
    handler = RunAiReviewHandler(
        FakeUnitOfWorkFactory(event_store=event_store), review_service
    )

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == []
