"""RunAiReview event handler tests."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from application.handlers.run_ai_review import RunAiReviewHandler
from application.ports.event_store import StoredEvent
from domain.adr import (
    ADRSubmittedForReview,
    AIReviewCompleted,
    AIReviewFailed,
    AdrContent,
    AdrId,
)
from domain.adr.required_sections import SectionName
from domain.adr.static_review import synthesize_static_review
from domain.adr.value_objects import (
    ReviewResult,
    SectionRating,
)
from domain.errors import InternalError, RetryableInternalError
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
    def __init__(
        self,
        *,
        results: list[ReviewResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._results = list(results or [])
        self._error = error
        self.calls: list[str] = []

    async def review_adr(
        self,
        markdown: str,
        *,
        validation_feedback: tuple[str, ...] = (),
    ) -> ReviewResult:
        del validation_feedback
        self.calls.append(markdown)
        if self._error is not None:
            raise self._error
        if not self._results:
            msg = "No fake review results configured"
            raise RuntimeError(msg)
        return self._results.pop(0)


def _valid_result(markdown: str) -> ReviewResult:
    static_annotations, static_ratings = synthesize_static_review(markdown)
    gap_sections = {rating.section for rating in static_ratings}
    llm_ratings = tuple(
        SectionRating(section=section, score=3, feedback="Adequate content.")
        for section in SectionName
        if section not in gap_sections
    )
    return ReviewResult(
        annotations=static_annotations,
        reviewed_at=_REVIEWED_AT,
        reviewed_content=markdown,
        section_ratings=(*static_ratings, *llm_ratings),
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

    assert review_service.calls == [content]
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
    assert len(applied_result.section_ratings) == 5
    processed_ids = [
        processed_id for processed_id, _ in persist_uow.event_store.marked_processed
    ]
    assert stored_event.id in processed_ids
    assert len(processed_ids) == 2


def test_run_ai_review_fails_when_service_raises_adr_review_failed_error() -> None:
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
    review_service = FakeAdrReviewService(
        error=RetryableInternalError("LLM review failed for Context after 2 attempts"),
    )
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = RunAiReviewHandler(uow_factory, review_service)

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == [content]
    persist_uow = uow_factory.unit_of_works[1]
    events, _, _ = persist_uow.event_store.appended[0]
    assert isinstance(events[0], AIReviewFailed)
    assert events[0].source_event_id == event_id
    assert events[0].kind == "retryable_internal_error"
    _, review_error, _ = persist_uow.adr_projection.recorded_failures[0]
    assert review_error.kind == "retryable_internal_error"
    assert "LLM review failed" in review_error.message


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (RuntimeError("provider down"), "retryable_internal_error"),
        (
            RetryableInternalError("LLM review failed for Context after 2 attempts"),
            "retryable_internal_error",
        ),
        (
            InternalError("Section Context has no body"),
            "internal_error",
        ),
    ],
)
def test_run_ai_review_fails_on_single_service_exception(
    error: Exception,
    expected_code: str,
) -> None:
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
    review_service = FakeAdrReviewService(error=error)
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = RunAiReviewHandler(uow_factory, review_service)

    asyncio.run(handler.handle(stored_event))

    assert len(review_service.calls) == 1
    persist_uow = uow_factory.unit_of_works[1]
    events, _, _ = persist_uow.event_store.appended[0]
    assert isinstance(events[0], AIReviewFailed)
    assert events[0].source_event_id == event_id
    _, review_error, _ = persist_uow.adr_projection.recorded_failures[0]
    assert review_error.kind == expected_code
    assert str(error) in review_error.message


def test_run_ai_review_fails_when_merged_result_fails_validation() -> None:
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
    invalid_result = ReviewResult(
        annotations=(),
        reviewed_at=_REVIEWED_AT,
        section_ratings=(),
    )
    review_service = FakeAdrReviewService(results=[invalid_result])
    uow_factory = FakeUnitOfWorkFactory(event_store=event_store)
    handler = RunAiReviewHandler(uow_factory, review_service)

    asyncio.run(handler.handle(stored_event))

    persist_uow = uow_factory.unit_of_works[1]
    events, _, _ = persist_uow.event_store.appended[0]
    assert isinstance(events[0], AIReviewFailed)
    assert events[0].kind == "internal_error"
    assert "Review validation failed" in events[0].message
    _, review_error, _ = persist_uow.adr_projection.recorded_failures[0]
    assert review_error.kind == "internal_error"
    assert persist_uow.adr_projection.applied_results == []


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
