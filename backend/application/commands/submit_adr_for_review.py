from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from application.ports.adr_repository import AdrRepository
from application.ports.event_store import StoredEvent
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.adr import ADRSubmittedForReview, AdrContent, AdrId, AdrStatus
from domain.errors import AdrNotFound, DomainError
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

    async def handle(
        self, command: SubmitAdrForReviewCommand
    ) -> SubmitAdrForReviewResult:
        existing = await self._adr_repository.find_by_id_for_owner(
            command.adr_id,
            command.user_id,
        )
        if existing is None:
            raise AdrNotFound()

        if existing.status != AdrStatus.DRAFT.value:
            raise DomainError("ADR can only be submitted from draft status")

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
            return SubmitAdrForReviewResult(stored_event=stored_events[0])
