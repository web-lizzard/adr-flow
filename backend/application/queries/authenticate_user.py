from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from application.ports.password_hasher import PasswordHasher
from application.ports.user_repository import UserRepository
from domain.errors import InvalidCredentials
from domain.user.value_objects import EmailAddress


@dataclass(frozen=True, slots=True)
class AuthenticateUserQuery:
    email: str
    password: str


class AuthenticateUserQueryHandler:
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    async def handle(self, query: AuthenticateUserQuery) -> UUID:
        try:
            email = EmailAddress(query.email)
        except ValidationError:
            raise InvalidCredentials() from None

        user = await self._user_repository.find_by_email(email.value)
        if user is None or not self._password_hasher.verify(
            query.password, user.password_hash
        ):
            raise InvalidCredentials()
        return user.id
