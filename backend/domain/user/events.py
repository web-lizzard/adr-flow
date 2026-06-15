from domain.events import DomainEvent
from domain.user.value_objects import EmailAddress, PasswordHash, UserId


class UserRegistered(DomainEvent):
    user_id: UserId
    email: EmailAddress
    password_hash: PasswordHash
