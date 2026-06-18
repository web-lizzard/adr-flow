from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from application.logging import get_logger
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.adr import ADR_STARTER_TEMPLATE, ADRCreated, AdrContent, AdrId, AdrTitle
from domain.adr.aggregate import ADR
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class CreateAdrCommand:
    user_id: UUID
    title: str


class CreateAdrCommandHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory
        self._logger = get_logger(__name__)

    async def handle(self, command: CreateAdrCommand) -> UUID:
        user_id = str(command.user_id)
        self._logger.info(
            "command.create_adr.started",
            user_id=user_id,
            title=command.title,
        )

        async with self._uow_factory.begin() as uow:
            adr_id = uuid4()
            await uow.lock_aggregate(adr_id)
            occurred_at = datetime.now(UTC)
            title = AdrTitle(command.title)
            content = AdrContent(ADR_STARTER_TEMPLATE)
            adr = ADR.create(
                adr_id=AdrId(adr_id),
                user_id=UserId(command.user_id),
                title=title,
                content=content,
                created_at=occurred_at,
            )

            event = ADRCreated(
                adr_id=adr.adr_id,
                user_id=adr.user_id,
                title=adr.title,
                content=adr.content,
                occurred_at=occurred_at,
            )

            stored_events = await uow.event_store.append(
                [event],
                aggregate_id=adr_id,
                aggregate_type="adr",
            )
            await uow.event_store.mark_processed(
                stored_events[0].id,
                processed_at=occurred_at,
            )

            await uow.adr_projection.insert(adr)
            self._logger.info(
                "command.create_adr.completed",
                adr_id=str(adr_id),
                user_id=user_id,
                title=command.title,
            )
            return adr_id
