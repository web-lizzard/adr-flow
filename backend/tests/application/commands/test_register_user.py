"""RegisterUser command handler tests."""

import asyncio


from application.commands.register_user import (
    RegisterUserCommand,
    RegisterUserCommandHandler,
)
from domain.user.events import UserRegistered
from tests.application.commands.fakes import FakeUnitOfWorkFactory


class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hash: str) -> bool:
        return self.hash(password) == hash


def test_register_user_emits_event_and_inserts_projection() -> None:
    uow_factory = FakeUnitOfWorkFactory()
    handler = RegisterUserCommandHandler(uow_factory, FakePasswordHasher())

    user_id = asyncio.run(
        handler.handle(RegisterUserCommand(email="user@example.com", password="secret"))
    )

    uow = uow_factory.unit_of_works[0]
    assert uow.locked_aggregates == [user_id]
    events, aggregate_id, aggregate_type = uow.event_store.appended[0]
    assert aggregate_id == user_id
    assert aggregate_type == "User"
    event = events[0]
    assert isinstance(event, UserRegistered)
    assert event.email.value == "user@example.com"
    assert event.password_hash.value == "hashed:secret"

    assert len(uow.user_projection.inserted) == 1
    inserted_id, email, password_hash, _created_at = uow.user_projection.inserted[0]
    assert inserted_id == user_id
    assert email == "user@example.com"
    assert password_hash == "hashed:secret"
