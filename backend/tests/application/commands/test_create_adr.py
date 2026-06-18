"""CreateAdr command handler tests."""

import asyncio
from uuid import uuid4

from application.commands.create_adr import CreateAdrCommand, CreateAdrCommandHandler
from domain.adr import ADR_STARTER_TEMPLATE, ADRCreated, AdrStatus
from tests.application.commands.fakes import FakeUnitOfWorkFactory


def test_create_adr_emits_event_and_inserts_projection_with_starter_template() -> None:
    user_id = uuid4()
    uow_factory = FakeUnitOfWorkFactory()
    handler = CreateAdrCommandHandler(uow_factory)

    adr_id = asyncio.run(
        handler.handle(CreateAdrCommand(user_id=user_id, title="My ADR"))
    )

    uow = uow_factory.unit_of_works[0]
    assert uow.locked_aggregates == [adr_id]
    assert len(uow.event_store.appended) == 1
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == adr_id
    assert aggregate_type == "adr"
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ADRCreated)
    assert event.title.value == "My ADR"
    assert event.content.value == ADR_STARTER_TEMPLATE

    assert len(uow.adr_projection.inserted) == 1
    inserted = uow.adr_projection.inserted[0]
    assert inserted.adr_id.value == adr_id
    assert inserted.user_id.value == user_id
    assert inserted.title.value == "My ADR"
    assert inserted.content.value == ADR_STARTER_TEMPLATE
    assert inserted.status == AdrStatus.DRAFT
