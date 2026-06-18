from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from application.logging import get_logger
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.adr import ADRPublished, AdrId
from domain.adr.rehydrate import rehydrate_adr
from domain.errors import AdrInvalidPublishStatus, AdrNotFound


@dataclass(frozen=True, slots=True)
class PublishAdrCommand:
    adr_id: UUID
    user_id: UUID


class PublishAdrCommandHandler:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory
        self._logger = get_logger(__name__)

    async def handle(self, command: PublishAdrCommand) -> None:
        adr_id = str(command.adr_id)
        user_id = str(command.user_id)
        self._logger.info(
            "command.publish_adr.started",
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
                    "command.publish_adr.rejected",
                    reason="adr_not_found",
                    adr_id=adr_id,
                )
                raise AdrNotFound()

            updated_at = datetime.now(UTC)
            adr.publish(updated_at)
            event = ADRPublished(
                adr_id=AdrId(command.adr_id),
                occurred_at=updated_at,
            )

            stored_events = await uow.event_store.append(
                [event],
                aggregate_id=command.adr_id,
                aggregate_type="adr",
            )
            transitioned = await uow.adr_projection.mark_proposed(
                command.adr_id,
                updated_at=updated_at,
            )
            if not transitioned:
                self._logger.info(
                    "command.publish_adr.rejected",
                    reason="invalid_status",
                    current_status=adr.status.value,
                    adr_id=adr_id,
                )
                raise AdrInvalidPublishStatus()
            stored_event = stored_events[0]
            stored_event_id = str(stored_event.id)
            await uow.event_store.mark_processed(
                stored_event.id,
                processed_at=updated_at,
            )
            self._logger.info(
                "command.publish_adr.event_appended",
                adr_id=adr_id,
                stored_event_id=stored_event_id,
            )
            self._logger.info(
                "command.publish_adr.completed",
                adr_id=adr_id,
                stored_event_id=stored_event_id,
            )
