from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from application.logging import get_logger
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.adr import ADRContentUpdated, AdrContent, AdrId, AdrTitle
from domain.adr.rehydrate import rehydrate_adr
from domain.errors import AdrNotFound


@dataclass(frozen=True, slots=True)
class UpdateAdrContentCommand:
    adr_id: UUID
    user_id: UUID
    title: str | None
    content: str | None


class UpdateAdrContentCommandHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory
        self._logger = get_logger(__name__)

    async def handle(self, command: UpdateAdrContentCommand) -> None:
        adr_id = str(command.adr_id)
        self._logger.info("command.update_adr_content.started", adr_id=adr_id)

        async with self._uow_factory.begin() as uow:
            await uow.lock_aggregate(command.adr_id)
            stored_events = await uow.event_store.load_stream(
                command.adr_id,
                "adr",
            )
            adr = rehydrate_adr([event.event for event in stored_events])
            if adr is None or adr.user_id.value != command.user_id:
                self._logger.info(
                    "command.update_adr_content.rejected",
                    reason="adr_not_found",
                    adr_id=adr_id,
                )
                raise AdrNotFound()

            updated_at = datetime.now(UTC)
            new_adr = adr
            event_title = None

            if command.content is not None:
                new_adr = new_adr.update_content(
                    AdrContent(command.content),
                    updated_at,
                )
            if command.title is not None:
                new_adr = new_adr.update_title(AdrTitle(command.title), updated_at)
                event_title = new_adr.title

            event = ADRContentUpdated(
                adr_id=AdrId(command.adr_id),
                content=new_adr.content,
                title=event_title,
                occurred_at=updated_at,
            )
            stored = await uow.event_store.append(
                [event],
                aggregate_id=command.adr_id,
                aggregate_type="adr",
            )
            await uow.event_store.mark_processed(
                stored[0].id,
                processed_at=updated_at,
            )

            await uow.adr_projection.update_content(new_adr)
            self._logger.info(
                "command.update_adr_content.completed",
                adr_id=adr_id,
                has_title_change=command.title is not None,
                has_content_change=command.content is not None,
            )
