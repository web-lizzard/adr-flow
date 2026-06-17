from datetime import UTC, datetime

from application.ports.adr_repository import AdrRepository
from application.ports.event_store import StoredEvent
from application.ports.llm_reviewer import LlmReviewer
from application.ports.unit_of_work import UnitOfWorkFactory
from application.review_metadata import ReviewErrorMetadata
from application.review_quality import validate_review_result
from domain.adr import ADRSubmittedForReview, AIReviewCompleted, AIReviewFailed, AdrId
from domain.adr.value_objects import AdrStatus, ReviewResult


class RunAiReviewHandler:
    _MAX_ATTEMPTS = 2

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        adr_repository: AdrRepository,
        llm_reviewer: LlmReviewer,
    ) -> None:
        self._uow_factory = uow_factory
        self._adr_repository = adr_repository
        self._llm_reviewer = llm_reviewer

    async def handle(self, stored_event: StoredEvent) -> None:
        event = stored_event.event
        if not isinstance(event, ADRSubmittedForReview):
            return

        adr_id = event.adr_id.value
        user_id = event.user_id.value
        markdown = event.content.value

        adr = await self._adr_repository.find_by_id_for_owner(adr_id, user_id)
        if adr is None:
            await self._mark_processed(stored_event.id)
            return

        if adr.status == AdrStatus.AFTER_REVIEW:
            await self._mark_processed(stored_event.id)
            return

        if (
            adr.review_error is not None
            and adr.review_error.source_event_id == stored_event.id
        ):
            await self._mark_processed(stored_event.id)
            return

        last_error: str | None = None
        for _attempt in range(self._MAX_ATTEMPTS):
            try:
                result = await self._llm_reviewer.review(markdown)
                validation = validate_review_result(markdown, result)
                if validation.passed:
                    await self._complete_review(stored_event, adr_id, result)
                    return
                last_error = "; ".join(validation.failures)
            except Exception as exc:  # noqa: BLE001 - provider failures are retried
                last_error = str(exc)

        await self._fail_review(
            stored_event,
            adr_id,
            last_error or "Review failed",
        )

    async def _complete_review(
        self,
        stored_event: StoredEvent,
        adr_id,
        result: ReviewResult,
    ) -> None:
        occurred_at = datetime.now(UTC)
        completion_event = AIReviewCompleted(
            adr_id=AdrId(adr_id),
            review_result=result,
            occurred_at=occurred_at,
        )
        async with self._uow_factory.begin() as uow:
            stored_events = await uow.event_store.append(
                [completion_event],
                aggregate_id=adr_id,
                aggregate_type="adr",
            )
            await uow.adr_projection.apply_review_result(
                adr_id,
                review_result=result,
                updated_at=occurred_at,
            )
            await uow.event_store.mark_processed(
                stored_events[0].id,
                processed_at=occurred_at,
            )
            await uow.event_store.mark_processed(
                stored_event.id,
                processed_at=occurred_at,
            )

    async def _fail_review(
        self,
        stored_event: StoredEvent,
        adr_id,
        message: str,
    ) -> None:
        occurred_at = datetime.now(UTC)
        failure_event = AIReviewFailed(
            adr_id=AdrId(adr_id),
            source_event_id=stored_event.id,
            code="validation_failed",
            message=message,
            occurred_at=occurred_at,
        )
        review_error = ReviewErrorMetadata(
            source_event_id=stored_event.id,
            code="validation_failed",
            message=message,
            failed_at=occurred_at,
        )
        async with self._uow_factory.begin() as uow:
            stored_events = await uow.event_store.append(
                [failure_event],
                aggregate_id=adr_id,
                aggregate_type="adr",
            )
            await uow.adr_projection.record_review_failure(
                adr_id,
                review_error=review_error,
                updated_at=occurred_at,
            )
            await uow.event_store.mark_processed(
                stored_events[0].id,
                processed_at=occurred_at,
            )
            await uow.event_store.mark_processed(
                stored_event.id,
                processed_at=occurred_at,
            )

    async def _mark_processed(self, event_id) -> None:
        processed_at = datetime.now(UTC)
        async with self._uow_factory.begin() as uow:
            await uow.event_store.mark_processed(event_id, processed_at=processed_at)
