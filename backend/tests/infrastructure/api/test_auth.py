"""Auth API integration tests."""

import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.infrastructure.api.conftest import (
    auth_headers,
    clear_bearer_auth,
    login_and_get_token,
    register_and_get_token,
)

_JWT_SECRET = "test-jwt-secret-at-least-32-characters"
_OTHER_JWT_SECRET = "other-jwt-secret-also-32-chars-min"


def _future_exp(hours: int = 24) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


def _past_exp(hours: int = 24) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


def _me_with_bearer(client: TestClient, token: str):
    return client.get("/api/auth/me", headers=auth_headers(token))


def _tampered_token(token: str) -> str:
    header, payload, signature = token.split(".", 2)
    payload_bytes = bytearray(base64.urlsafe_b64decode(payload + "=="))
    payload_bytes[0] ^= 0x01
    tampered_payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    return f"{header}.{tampered_payload}.{signature}"


def test_register_returns_201_and_access_token(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "set-cookie" not in response.headers


def test_register_duplicate_email_returns_400(auth_client) -> None:
    payload = {"email": "alice@example.com", "password": "password123"}
    first = auth_client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = auth_client.post("/api/auth/register", json=payload)
    assert second.status_code == 400
    assert "detail" in second.json()


def test_login_with_correct_credentials_returns_200_and_access_token(
    auth_client,
) -> None:
    register_and_get_token(auth_client, "alice@example.com")

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert "set-cookie" not in response.headers

    me = auth_client.get("/api/auth/me", headers=auth_headers(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_login_with_wrong_password_returns_401(auth_client) -> None:
    register_and_get_token(auth_client, "alice@example.com")

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_is_case_insensitive_for_email(auth_client) -> None:
    register_and_get_token(auth_client, "Alice@Example.com")

    token = login_and_get_token(auth_client, "Alice@Example.com")
    response = auth_client.get("/api/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_with_valid_bearer_token_returns_200(auth_client) -> None:
    token = register_and_get_token(auth_client, "alice@example.com")

    response = auth_client.get("/api/auth/me", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_without_bearer_token_returns_401(auth_client) -> None:
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_with_tampered_bearer_token_returns_401(auth_client) -> None:
    valid_token = register_and_get_token(auth_client, "alice@example.com")

    response = _me_with_bearer(auth_client, _tampered_token(valid_token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_malformed_bearer_token_returns_401(auth_client) -> None:
    response = _me_with_bearer(auth_client, "not.a.jwt.at.all")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_expired_bearer_token_returns_401(auth_client) -> None:
    user_id = uuid4()
    expired_token = jwt.encode(
        {"sub": str(user_id), "exp": _past_exp()},
        _JWT_SECRET,
        algorithm="HS256",
    )

    response = _me_with_bearer(auth_client, expired_token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_wrong_secret_bearer_token_returns_401(auth_client) -> None:
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "exp": _future_exp()},
        _OTHER_JWT_SECRET,
        algorithm="HS256",
    )

    response = _me_with_bearer(auth_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_alg_none_bearer_token_returns_401(auth_client) -> None:
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "exp": _future_exp()},
        "",
        algorithm="none",
    )

    response = _me_with_bearer(auth_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_valid_token_for_deleted_user_returns_401(
    auth_client, db_engine
) -> None:
    token = register_and_get_token(auth_client, "deleted@example.com")

    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))

    response = _me_with_bearer(auth_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_future_nbf_bearer_token_returns_401_non_blocking(
    auth_client,
) -> None:
    """Non-blocking regression guard: PyJWT rejects not-yet-valid tokens by default."""
    user_id = uuid4()
    token = jwt.encode(
        {
            "sub": str(user_id),
            "exp": _future_exp(),
            "nbf": _future_exp(hours=48),
        },
        _JWT_SECRET,
        algorithm="HS256",
    )

    response = _me_with_bearer(auth_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_login_with_nonexistent_email_returns_same_401_as_wrong_password(
    auth_client,
) -> None:
    register_and_get_token(auth_client, "alice@example.com")

    wrong_password = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )
    unknown_email = auth_client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == "Invalid email or password"
    assert unknown_email.json()["detail"] == wrong_password.json()["detail"]


def test_login_with_invalid_email_format_returns_422(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/login",
        json={"email": "not-an-email", "password": "password123"},
    )

    assert response.status_code == 422


def test_register_with_password_shorter_than_8_chars_returns_422(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )

    assert response.status_code == 422


def test_register_with_exactly_8_char_password_returns_201(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "boundary@example.com", "password": "exactly8"},
    )

    assert response.status_code == 201
    assert "access_token" in response.json()


def test_register_with_empty_password_returns_422(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "empty@example.com", "password": ""},
    )

    assert response.status_code == 422


def test_register_accessible_without_bearer_token(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "public-register@example.com", "password": "password123"},
    )

    assert response.status_code == 201


def test_login_accessible_without_bearer_token(auth_client) -> None:
    register_and_get_token(auth_client, "public-login@example.com")
    clear_bearer_auth(auth_client)

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "public-login@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_health_endpoints_accessible_without_bearer_token(auth_client) -> None:
    assert auth_client.get("/health").status_code == 200
    assert auth_client.get("/api/health").status_code == 200


def test_register_persists_user_registered_event(auth_client, db_engine) -> None:
    register_and_get_token(auth_client, "alice@example.com")

    with db_engine.connect() as connection:
        result = connection.execute(
            text(
                "SELECT event_type, processed_at FROM events "
                "WHERE event_type = 'UserRegistered'"
            )
        )
        rows = result.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "UserRegistered"
    assert rows[0][1] is not None


def test_register_persists_users_projection_row(auth_client, db_engine) -> None:
    register_and_get_token(auth_client, "alice@example.com")

    with db_engine.connect() as connection:
        result = connection.execute(
            text("SELECT email FROM users WHERE email = 'alice@example.com'")
        )
        row = result.fetchone()

    assert row is not None
    assert row[0] == "alice@example.com"


def test_failed_register_leaves_no_orphan_rows(auth_client, db_engine) -> None:
    payload = {"email": "alice@example.com", "password": "password123"}
    auth_client.post("/api/auth/register", json=payload)
    auth_client.post("/api/auth/register", json=payload)

    with db_engine.connect() as connection:
        events = connection.execute(text("SELECT COUNT(*) FROM events")).scalar_one()
        users = connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one()

    assert events == 1
    assert users == 1
