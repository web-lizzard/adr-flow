"""User aggregate and rehydration tests."""

from datetime import UTC, datetime
from uuid import uuid4

from domain.user.aggregate import User
from domain.user.events import UserRegistered
from domain.user.rehydrate import rehydrate_user
from domain.user.value_objects import EmailAddress, PasswordHash, UserId

_NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)


def test_user_create_factory() -> None:
    user_id = UserId(uuid4())
    email = EmailAddress("alice@example.com")
    password_hash = PasswordHash("hashed-secret")

    user = User.create(
        user_id=user_id,
        email=email,
        password_hash=password_hash,
        created_at=_NOW,
    )

    assert user.user_id == user_id
    assert user.email == email
    assert user.password_hash == password_hash
    assert user.created_at == _NOW


def test_rehydrate_user_empty_stream_returns_none() -> None:
    assert rehydrate_user([]) is None


def test_rehydrate_user_from_registered_event() -> None:
    user_id = UserId(uuid4())
    email = EmailAddress("alice@example.com")
    password_hash = PasswordHash("hashed-secret")

    events = [
        UserRegistered(
            user_id=user_id,
            email=email,
            password_hash=password_hash,
            occurred_at=_NOW,
        )
    ]

    user = rehydrate_user(events)

    assert user is not None
    assert user.user_id == user_id
    assert user.email == email
    assert user.password_hash == password_hash
    assert user.created_at == _NOW
