from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from application.logging import get_logger
from application.ports.adr_repository import AdrRepository
from application.ports.unit_of_work import UnitOfWorkFactory
from domain.adr import ADR, ADRContentUpdated, AdrContent, AdrId, AdrStatus, AdrTitle
from domain.errors import AdrNotFound, AdrTitleAlreadyExists, DomainError
from domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class UpdateAdrContentCommand:
    adr_id: UUID
    user_id: UUID
    title: str | None
    content: str | None


class UpdateAdrContentCommandHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        adr_repository: AdrRepository,
    ) -> None:
        self._uow_factory = uow_factory
        self._adr_repository = adr_repository
        self._logger = get_logger(__name__)

    async def handle(self, command: UpdateAdrContentCommand) -> None:
        adr_id = str(command.adr_id)
        self._logger.info("command.update_adr_content.started", adr_id=adr_id)

        existing = await self._adr_repository.find_by_id_for_owner(
            command.adr_id,
            command.user_id,
        )
        if existing is None:
            self._logger.info(
                "command.update_adr_content.rejected",
                reason="adr_not_found",
                adr_id=adr_id,
            )
            raise AdrNotFound()

        if existing.status == AdrStatus.IN_REVIEW:
            self._logger.info(
                "command.update_adr_content.rejected",
                reason="in_review",
                adr_id=adr_id,
            )
            raise DomainError("Cannot edit ADR in review")

        new_title = command.title if command.title is not None else existing.title
        new_content = (
            command.content if command.content is not None else existing.content
        )

        if (
            command.title is not None
            and command.title.lower() != existing.title.lower()
        ):
            conflict = await self._adr_repository.find_by_title_for_owner(
                command.title,
                command.user_id,
            )
            if conflict is not None and conflict.id != existing.id:
                self._logger.info(
                    "command.update_adr_content.rejected",
                    reason="title_exists",
                    adr_id=adr_id,
                )
                raise AdrTitleAlreadyExists()

        updated_at = datetime.now(UTC)
        title = AdrTitle(new_title)
        content = AdrContent(new_content)
        event_title = title if command.title is not None else None

        async with self._uow_factory.begin() as uow:
            event = ADRContentUpdated(
                adr_id=AdrId(command.adr_id),
                content=content,
                title=event_title,
                occurred_at=updated_at,
            )
            stored_events = await uow.event_store.append(
                [event],
                aggregate_id=command.adr_id,
                aggregate_type="adr",
            )
            await uow.event_store.mark_processed(
                stored_events[0].id,
                processed_at=updated_at,
            )

            adr = ADR(
                adr_id=AdrId(existing.id),
                user_id=UserId(existing.user_id),
                title=title,
                content=content,
                status=AdrStatus(existing.status),
                review_result=None,
                is_deleted=existing.is_deleted,
                created_at=existing.created_at,
                updated_at=updated_at,
            )
            await uow.adr_projection.update_content(adr)
            self._logger.info(
                "command.update_adr_content.completed",
                adr_id=adr_id,
                has_title_change=command.title is not None,
                has_content_change=command.content is not None,
            )
