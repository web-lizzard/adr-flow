from datetime import UTC, datetime

from application.logging import get_logger
from application.ports.adr_repository import AdrRepository
from application.ports.adr_review import AdrReviewPort
from application.ports.event_store import StoredEvent
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
        adr_review_service: AdrReviewPort,
    ) -> None:
        self._uow_factory = uow_factory
        self._adr_repository = adr_repository
        self._adr_review_service = adr_review_service
        self._logger = get_logger(__name__)

    async def handle(self, stored_event: StoredEvent) -> None:
        event = stored_event.event
        if not isinstance(event, ADRSubmittedForReview):
            self._logger.info(
                "handler.run_ai_review.skipped",
                reason="wrong_event_type",
            )
            return

        adr_id = event.adr_id.value
        user_id = event.user_id.value
        markdown = event.content.value

        self._logger.info(
            "handler.run_ai_review.started",
            stored_event_id=str(stored_event.id),
            adr_id=str(adr_id),
            user_id=str(user_id),
        )

        adr = await self._adr_repository.find_by_id_for_owner(adr_id, user_id)
        if adr is None:
            self._logger.info(
                "handler.run_ai_review.skipped",
                reason="adr_not_found",
                adr_id=str(adr_id),
            )
            await self._mark_processed(stored_event.id)
            return

        if adr.status == AdrStatus.AFTER_REVIEW:
            self._logger.info(
                "handler.run_ai_review.skipped",
                reason="already_reviewed",
                adr_id=str(adr_id),
                status=adr.status,
            )
            await self._mark_processed(stored_event.id)
            return

        if (
            adr.review_error is not None
            and adr.review_error.source_event_id == stored_event.id
        ):
            self._logger.info(
                "handler.run_ai_review.skipped",
                reason="duplicate_failure",
                adr_id=str(adr_id),
                source_event_id=str(stored_event.id),
            )
            await self._mark_processed(stored_event.id)
            return

        last_error: str | None = None
        validation_feedback: tuple[str, ...] = ()
        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            self._logger.info(
                "handler.run_ai_review.attempt",
                adr_id=str(adr_id),
                attempt=attempt,
                max_attempts=self._MAX_ATTEMPTS,
            )
            try:
                self._logger.info(
                    "handler.run_ai_review.llm_call_started",
                    adr_id=str(adr_id),
                    attempt=attempt,
                    content_length=len(markdown),
                )
                result = await self._adr_review_service.review_adr(
                    markdown,
                    validation_feedback=validation_feedback,
                )
                validation = validate_review_result(markdown, result)
                if validation.passed:
                    annotation_count = len(result.annotations)
                    await self._complete_review(stored_event, adr_id, result)
                    self._logger.info(
                        "handler.run_ai_review.completed",
                        adr_id=str(adr_id),
                        annotation_count=annotation_count,
                    )
                    return
                last_error = "; ".join(validation.failures)
                validation_feedback = validation.failures
                self._logger.warning(
                    "handler.run_ai_review.validation_failed",
                    adr_id=str(adr_id),
                    attempt=attempt,
                    failures=validation.failures,
                )
            except Exception as exc:  # noqa: BLE001 - provider failures are retried
                last_error = str(exc)
                if attempt == self._MAX_ATTEMPTS:
                    self._logger.error(
                        "handler.run_ai_review.llm_call_failed",
                        adr_id=str(adr_id),
                        attempt=attempt,
                        error=last_error,
                        exc_info=True,
                    )
                else:
                    self._logger.warning(
                        "handler.run_ai_review.llm_call_failed",
                        adr_id=str(adr_id),
                        attempt=attempt,
                        error=last_error,
                    )

        self._logger.error(
            "handler.run_ai_review.failed",
            adr_id=str(adr_id),
            last_error=last_error or "Review failed",
            attempts=self._MAX_ATTEMPTS,
        )
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
        completion_event_id = None
        async with self._uow_factory.begin() as uow:
            stored_events = await uow.event_store.append(
                [completion_event],
                aggregate_id=adr_id,
                aggregate_type="adr",
            )
            completion_event_id = stored_events[0].id
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
        self._logger.info(
            "handler.run_ai_review.persistence_completed",
            completion_event_id=str(completion_event_id),
            source_event_id=str(stored_event.id),
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
        self._logger.info(
            "handler.run_ai_review.failure_persisted",
            code="validation_failed",
            message=message,
        )

    async def _mark_processed(self, event_id) -> None:
        processed_at = datetime.now(UTC)
        async with self._uow_factory.begin() as uow:
            await uow.event_store.mark_processed(event_id, processed_at=processed_at)
        self._logger.info(
            "handler.run_ai_review.marked_processed",
            event_id=str(event_id),
        )
