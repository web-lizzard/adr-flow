from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from application.logging import get_logger
from application.ports.adr_repository import AdrRepository
from application.ports.event_store import StoredEvent
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.adr import ADRSubmittedForReview, AdrContent, AdrId, AdrStatus
from domain.errors import AdrInvalidSubmitStatus, AdrNotFound
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class SubmitAdrForReviewCommand:
    adr_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class SubmitAdrForReviewResult:
    stored_event: StoredEvent


class SubmitAdrForReviewCommandHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        adr_repository: AdrRepository,
    ) -> None:
        self._uow_factory = uow_factory
        self._adr_repository = adr_repository
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

        existing = await self._adr_repository.find_by_id_for_owner(
            command.adr_id,
            command.user_id,
        )
        if existing is None:
            self._logger.info(
                "command.submit_adr_for_review.rejected",
                reason="adr_not_found",
                adr_id=adr_id,
            )
            raise AdrNotFound()

        if existing.status != AdrStatus.DRAFT.value:
            self._logger.info(
                "command.submit_adr_for_review.rejected",
                reason="invalid_status",
                current_status=existing.status,
                adr_id=adr_id,
            )
            raise AdrInvalidSubmitStatus()

        updated_at = datetime.now(UTC)
        event = ADRSubmittedForReview(
            adr_id=AdrId(command.adr_id),
            user_id=UserId(command.user_id),
            content=AdrContent(existing.content),
            occurred_at=updated_at,
        )

        async with self._uow_factory.begin() as uow:
            stored_events = await uow.event_store.append(
                [event],
                aggregate_id=command.adr_id,
                aggregate_type="adr",
            )
            await uow.adr_projection.mark_in_review(
                command.adr_id,
                updated_at=updated_at,
            )
            stored_event = stored_events[0]
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
