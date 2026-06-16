from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

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

    async def handle(self, command: CreateAdrCommand) -> UUID:
        existing = await self._adr_repository.find_by_title_for_owner(
            command.title,
            command.user_id,
        )
        if existing is not None:
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

            await uow.event_store.append(
                [event],
                aggregate_id=adr_id,
                aggregate_type="adr",
            )

            adr = ADR(
                adr_id=AdrId(adr_id),
                user_id=UserId(command.user_id),
                title=title,
                content=content,
                status=AdrStatus.DRAFT,
                review_result=None,
                is_deleted=False,
                created_at=occurred_at,
                updated_at=occurred_at,
            )
            await uow.adr_projection.insert(adr)
            return adr_id
