"""User domain vocabulary construction tests."""

from datetime import UTC, datetime
from uuid import uuid4

from domain.user import EmailAddress, PasswordHash, User, UserId, UserRegistered


def test_user_value_objects_and_aggregate_construct() -> None:
    user_id = UserId(uuid4())
    email = EmailAddress("alice@example.com")
    password_hash = PasswordHash("hashed-secret")
    created_at = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)

    user = User(
        user_id=user_id,
        email=email,
        password_hash=password_hash,
        created_at=created_at,
    )

    assert user.user_id == user_id
    assert user.email.value == "alice@example.com"
    assert user.password_hash.value == "hashed-secret"
    assert user.created_at == created_at


def test_user_registered_event_construct() -> None:
    user_id = UserId(uuid4())
    email = EmailAddress("alice@example.com")
    password_hash = PasswordHash("hashed-secret")
    occurred_at = datetime(2026, 6, 14, 12, 0, tzinfo=UTC)

    event = UserRegistered(
        user_id=user_id,
        email=email,
        password_hash=password_hash,
        occurred_at=occurred_at,
    )

    assert event.__class__.__name__ == "UserRegistered"
    assert event.user_id == user_id
    assert event.occurred_at == occurred_at
