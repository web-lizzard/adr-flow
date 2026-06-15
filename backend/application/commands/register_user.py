from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import ValidationError

from application.ports.password_hasher import PasswordHasher
from application.ports.unit_of_work import UnitOfWorkFactory
from application.ports.user_repository import UserRepository
from application.validation import value_error_from_pydantic
from domain.errors import EmailAlreadyTaken
from domain.user.errors import InvalidEmailAddress
from domain.user.events import UserRegistered
from domain.user.value_objects import EmailAddress, PasswordHash, UserId


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    password: str


class RegisterUserCommandHandler:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._uow_factory = uow_factory
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    async def handle(self, command: RegisterUserCommand) -> UUID:
        try:
            email = EmailAddress(command.email)
        except ValidationError as exc:
            raise value_error_from_pydantic(exc, InvalidEmailAddress) from exc

        existing = await self._user_repository.find_by_email(email.value)
        if existing is not None:
            raise EmailAlreadyTaken()

        async with self._uow_factory.begin() as uow:
            user_id = uuid4()
            password_hash = self._password_hasher.hash(command.password)
            occurred_at = datetime.now(UTC)

            event = UserRegistered(
                user_id=UserId(user_id),
                email=email,
                password_hash=PasswordHash(password_hash),
                occurred_at=occurred_at,
            )

            await uow.event_store.append(
                [event],
                aggregate_id=user_id,
                aggregate_type="User",
            )
            await uow.user_projection.insert(
                user_id=user_id,
                email=email.value,
                password_hash=password_hash,
                created_at=occurred_at,
            )
            return user_id
