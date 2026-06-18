"""RunAiReview event handler tests."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4


from application.handlers.run_ai_review import RunAiReviewHandler
from application.ports.adr_repository import AdrReadModel
from application.ports.event_store import StoredEvent
from application.review_metadata import ReviewErrorMetadata
from domain.adr import (
    ADRSubmittedForReview,
    AIReviewCompleted,
    AIReviewFailed,
    AdrContent,
    AdrId,
    AdrStatus,
)
from domain.adr.value_objects import (
    ReviewAnnotation,
    ReviewAnnotationKind,
    ReviewResult,
)
from domain.user.value_objects import UserId

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


class FakeEventStore:
    def __init__(self) -> None:
        self.appended: list[tuple[list, UUID, str]] = []
        self.marked_processed: list[tuple[UUID, datetime]] = []

    async def append(
        self, events: list, aggregate_id: UUID, aggregate_type: str
    ) -> list[StoredEvent]:
        self.appended.append((events, aggregate_id, aggregate_type))
        stored: list[StoredEvent] = []
        for event in events:
            stored.append(
                StoredEvent(
                    id=uuid4(),
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    event=event,
                    occurred_at=event.occurred_at,
                )
            )
        return stored

    async def load_unprocessed(self, *, limit: int = 100) -> list[StoredEvent]:
        return []

    async def mark_processed(self, event_id: UUID, *, processed_at: datetime) -> None:
        self.marked_processed.append((event_id, processed_at))


class FakeAdrProjection:
    def __init__(self) -> None:
        self.applied_results: list[tuple[UUID, ReviewResult, datetime]] = []
        self.recorded_failures: list[tuple[UUID, ReviewErrorMetadata, datetime]] = []

    async def insert(self, adr) -> None:
        return None

    async def update_content(self, adr) -> None:
        return None

    async def mark_in_review(self, adr_id: UUID, *, updated_at: datetime) -> None:
        return None

    async def mark_proposed(self, adr_id: UUID, *, updated_at: datetime) -> bool:
        return True

    async def apply_review_result(
        self,
        adr_id: UUID,
        *,
        review_result: ReviewResult,
        updated_at: datetime,
    ) -> None:
        self.applied_results.append((adr_id, review_result, updated_at))

    async def record_review_failure(
        self,
        adr_id: UUID,
        *,
        review_error: ReviewErrorMetadata,
        updated_at: datetime,
    ) -> None:
        self.recorded_failures.append((adr_id, review_error, updated_at))


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.event_store = FakeEventStore()
        self.adr_projection = FakeAdrProjection()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeUnitOfWorkFactory:
    def __init__(self) -> None:
        self.unit_of_works: list[FakeUnitOfWork] = []

    @asynccontextmanager
    async def begin(self):
        uow = FakeUnitOfWork()
        self.unit_of_works.append(uow)
        yield uow


class FakeAdrRepository:
    def __init__(self, *, by_id: AdrReadModel | None = None) -> None:
        self._by_id = by_id

    async def find_by_id_for_owner(
        self, adr_id: UUID, user_id: UUID
    ) -> AdrReadModel | None:
        if self._by_id is None:
            return None
        if self._by_id.id != adr_id or self._by_id.user_id != user_id:
            return None
        return self._by_id

    async def find_by_title_for_owner(
        self, title: str, user_id: UUID
    ) -> AdrReadModel | None:
        return None

    async def search_by_title(self, user_id: UUID, query: str) -> list[AdrReadModel]:
        return []

    async def list_for_owner(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdrReadModel]:
        return []


def _adr_read_model(
    *,
    adr_id: UUID,
    user_id: UUID,
    content: str,
    status: str = AdrStatus.IN_REVIEW.value,
    review_error: ReviewErrorMetadata | None = None,
) -> AdrReadModel:
    now = datetime(2026, 6, 17, 10, 0, tzinfo=UTC)
    return AdrReadModel(
        id=adr_id,
        user_id=user_id,
        title="Review ADR",
        content=content,
        status=status,
        is_deleted=False,
        created_at=now,
        updated_at=now,
        review_error=review_error,
    )


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
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content
    )
    repository = FakeAdrRepository(
        by_id=_adr_read_model(adr_id=adr_id, user_id=user_id, content=content)
    )
    review_service = FakeAdrReviewService(results=[_valid_result(content)])
    uow_factory = FakeUnitOfWorkFactory()
    handler = RunAiReviewHandler(uow_factory, repository, review_service)

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == [(content, ())]
    uow = uow_factory.unit_of_works[0]
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    assert len(events) == 1
    assert isinstance(events[0], AIReviewCompleted)

    applied_id, applied_result, _ = uow.adr_projection.applied_results[0]
    assert applied_id == adr_id
    assert applied_result.reviewed_content == content
    processed_ids = [event_id for event_id, _ in uow.event_store.marked_processed]
    assert stored_event.id in processed_ids
    assert len(processed_ids) == 2


def test_run_ai_review_retries_once_on_invalid_output_then_succeeds() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nWe need a store.\n\n## Options\n\nA or B.\n"
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content
    )
    invalid = ReviewResult(annotations=(), reviewed_at=_REVIEWED_AT)
    valid = _valid_result(content)
    repository = FakeAdrRepository(
        by_id=_adr_read_model(adr_id=adr_id, user_id=user_id, content=content)
    )
    review_service = FakeAdrReviewService(results=[invalid, valid])
    handler = RunAiReviewHandler(FakeUnitOfWorkFactory(), repository, review_service)

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
        adr_id=adr_id,
        user_id=user_id,
        content=content,
        event_id=event_id,
    )
    invalid = ReviewResult(annotations=(), reviewed_at=_REVIEWED_AT)
    repository = FakeAdrRepository(
        by_id=_adr_read_model(adr_id=adr_id, user_id=user_id, content=content)
    )
    review_service = FakeAdrReviewService(results=[invalid, invalid])
    uow_factory = FakeUnitOfWorkFactory()
    handler = RunAiReviewHandler(uow_factory, repository, review_service)

    asyncio.run(handler.handle(stored_event))

    uow = uow_factory.unit_of_works[0]
    events, _, _ = uow.event_store.appended[0]
    assert isinstance(events[0], AIReviewFailed)
    assert events[0].source_event_id == event_id

    _, review_error, _ = uow.adr_projection.recorded_failures[0]
    assert review_error.source_event_id == event_id
    assert review_error.code == "validation_failed"
    processed_ids = [event_id for event_id, _ in uow.event_store.marked_processed]
    assert event_id in processed_ids
    assert len(processed_ids) == 2


def test_run_ai_review_is_idempotent_when_adr_already_after_review() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nDone"
    stored_event = _stored_submitted_event(
        adr_id=adr_id, user_id=user_id, content=content
    )
    repository = FakeAdrRepository(
        by_id=_adr_read_model(
            adr_id=adr_id,
            user_id=user_id,
            content=content,
            status=AdrStatus.AFTER_REVIEW.value,
        )
    )
    review_service = FakeAdrReviewService()
    uow_factory = FakeUnitOfWorkFactory()
    handler = RunAiReviewHandler(uow_factory, repository, review_service)

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == []
    uow = uow_factory.unit_of_works[0]
    assert uow.event_store.appended == []
    assert uow.event_store.marked_processed[0][0] == stored_event.id


def test_run_ai_review_skips_when_failure_already_recorded_for_event() -> None:
    adr_id = uuid4()
    user_id = uuid4()
    content = "## Context\n\nDone"
    event_id = uuid4()
    stored_event = _stored_submitted_event(
        adr_id=adr_id,
        user_id=user_id,
        content=content,
        event_id=event_id,
    )
    repository = FakeAdrRepository(
        by_id=_adr_read_model(
            adr_id=adr_id,
            user_id=user_id,
            content=content,
            review_error=ReviewErrorMetadata(
                source_event_id=event_id,
                code="validation_failed",
                message="Already failed",
                failed_at=_REVIEWED_AT,
            ),
        )
    )
    review_service = FakeAdrReviewService()
    handler = RunAiReviewHandler(FakeUnitOfWorkFactory(), repository, review_service)

    asyncio.run(handler.handle(stored_event))

    assert review_service.calls == []
