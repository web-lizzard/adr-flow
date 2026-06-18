from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from application.logging import get_logger
from application.ports.adr_repository import AdrRepository
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.adr import (
    ADR,
    ADR_STARTER_TEMPLATE,
    ADRCreated,
    AdrContent,
    AdrId,
    AdrStatus,
    AdrTitle,
)
from domain.errors import AdrTitleAlreadyExists
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class CreateAdrCommand:
    user_id: UUID
    title: str


class CreateAdrCommandHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        adr_repository: AdrRepository,
    ) -> None:
        self._uow_factory = uow_factory
        self._adr_repository = adr_repository
        self._logger = get_logger(__name__)

    async def handle(self, command: CreateAdrCommand) -> UUID:
        user_id = str(command.user_id)
        self._logger.info(
            "command.create_adr.started",
            user_id=user_id,
            title=command.title,
        )

        existing = await self._adr_repository.find_by_title_for_owner(
            command.title,
            command.user_id,
        )
        if existing is not None:
            self._logger.info(
                "command.create_adr.rejected",
                reason="title_exists",
                title=command.title,
            )
            raise AdrTitleAlreadyExists()

        async with self._uow_factory.begin() as uow:
            adr_id = uuid4()
            occurred_at = datetime.now(UTC)
            title = AdrTitle(command.title)
            content = AdrContent(ADR_STARTER_TEMPLATE)

            event = ADRCreated(
                adr_id=AdrId(adr_id),
                user_id=UserId(command.user_id),
                title=title,
                content=content,
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

            adr = ADR(
                adr_id=AdrId(adr_id),
                user_id=UserId(command.user_id),
                title=title,
                content=content,
                status=AdrStatus.DRAFT,
                review_result=None,
                review_error=None,
                is_deleted=False,
                created_at=occurred_at,
                updated_at=occurred_at,
            )
            await uow.adr_projection.insert(adr)
            self._logger.info(
                "command.create_adr.completed",
                adr_id=str(adr_id),
                user_id=user_id,
                title=command.title,
            )
            return adr_id
