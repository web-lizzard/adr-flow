from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from application.logging import get_logger
from application.ports.event_store import StoredEvent
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.adr import ADRSubmittedForReview, AdrId
from domain.adr.rehydrate import rehydrate_adr
from domain.errors import AdrNotFound
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class SubmitAdrForReviewCommand:
    adr_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class SubmitAdrForReviewResult:
    stored_event: StoredEvent


class SubmitAdrForReviewCommandHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory
        self._logger = get_logger(__name__)

    async def handle(
        self, command: SubmitAdrForReviewCommand
    ) -> SubmitAdrForReviewResult:
        adr_id = str(command.adr_id)
        user_id = str(command.user_id)
        self._logger.info(
            "command.submit_adr_for_review.started",
            adr_id=adr_id,
            user_id=user_id,
        )

        async with self._uow_factory.begin() as uow:
            await uow.lock_aggregate(command.adr_id)
            stored_events = await uow.event_store.load_stream(
                command.adr_id,
                "adr",
            )
            adr = rehydrate_adr([event.event for event in stored_events])
            if adr is None or adr.user_id.value != command.user_id:
                self._logger.info(
                    "command.submit_adr_for_review.rejected",
                    reason="adr_not_found",
                    adr_id=adr_id,
                )
                raise AdrNotFound()

            updated_at = datetime.now(UTC)
            new_adr = adr.submit_for_review(updated_at)
            event = ADRSubmittedForReview(
                adr_id=AdrId(command.adr_id),
                user_id=UserId(command.user_id),
                content=new_adr.content,
                occurred_at=updated_at,
            )

            stored = await uow.event_store.append(
                [event],
                aggregate_id=command.adr_id,
                aggregate_type="adr",
            )
            await uow.adr_projection.mark_in_review(
                command.adr_id,
                updated_at=updated_at,
            )
            stored_event = stored[0]
            stored_event_id = str(stored_event.id)
            self._logger.info(
                "command.submit_adr_for_review.event_appended",
                adr_id=adr_id,
                stored_event_id=stored_event_id,
            )
            self._logger.info(
                "command.submit_adr_for_review.completed",
                adr_id=adr_id,
                stored_event_id=stored_event_id,
            )
            return SubmitAdrForReviewResult(stored_event=stored_event)
