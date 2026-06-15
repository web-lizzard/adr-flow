"""Auth API integration tests."""

import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text

from infrastructure.api.dependencies import SESSION_COOKIE_NAME
from infrastructure.bootstrap import create_app
from infrastructure.config import Settings

_JWT_SECRET = "test-jwt-secret-at-least-32-characters"
_OTHER_JWT_SECRET = "other-jwt-secret-also-32-chars-min"


def _future_exp(hours: int = 24) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


def _past_exp(hours: int = 24) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


def _me_with_session_cookie(client: TestClient, token: str):
    client.cookies.set(SESSION_COOKIE_NAME, token)
    return client.get("/api/auth/me")


def _tampered_token(token: str) -> str:
    header, payload, signature = token.split(".", 2)
    payload_bytes = bytearray(base64.urlsafe_b64decode(payload + "=="))
    payload_bytes[0] ^= 0x01
    tampered_payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    return f"{header}.{tampered_payload}.{signature}"


def _set_cookie_header(response) -> str:
    return response.headers["set-cookie"]


def _login_and_get_set_cookie(auth_client: TestClient) -> str:
    auth_client.post(
        "/api/auth/register",
        json={"email": "cookie-flags@example.com", "password": "password123"},
    )
    response = auth_client.post(
        "/api/auth/login",
        json={"email": "cookie-flags@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    return _set_cookie_header(response)


def test_register_returns_201_and_sets_cookie(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    assert SESSION_COOKIE_NAME in response.cookies
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body
    assert "created_at" in body


def test_register_default_cookie_path_matches_browser_api_contract(
    postgres_url,
) -> None:
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
        cookie_secure=False,
        cookie_path="/api",
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={"email": "cookie-path@example.com", "password": "password123"},
        )

    assert response.status_code == 201
    assert "Path=/api" in response.headers["set-cookie"]


def test_register_duplicate_email_returns_400(auth_client) -> None:
    payload = {"email": "alice@example.com", "password": "password123"}
    first = auth_client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = auth_client.post("/api/auth/register", json=payload)
    assert second.status_code == 400
    assert "detail" in second.json()


def test_login_with_correct_credentials_returns_200_and_cookie(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert SESSION_COOKIE_NAME in response.cookies
    assert response.json()["email"] == "alice@example.com"


def test_login_with_wrong_password_returns_401(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_is_case_insensitive_for_email(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "Alice@Example.com", "password": "password123"},
    )

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "Alice@Example.com", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_with_valid_cookie_returns_200(auth_client) -> None:
    register = auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert register.status_code == 201

    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_without_cookie_returns_401(auth_client) -> None:
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 401


def test_me_with_tampered_session_cookie_returns_401(auth_client) -> None:
    register = auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert register.status_code == 201
    valid_token = register.cookies[SESSION_COOKIE_NAME]

    response = _me_with_session_cookie(auth_client, _tampered_token(valid_token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_malformed_session_cookie_returns_401(auth_client) -> None:
    response = _me_with_session_cookie(auth_client, "not.a.jwt.at.all")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_expired_session_cookie_returns_401(auth_client) -> None:
    user_id = uuid4()
    expired_token = jwt.encode(
        {"sub": str(user_id), "exp": _past_exp()},
        _JWT_SECRET,
        algorithm="HS256",
    )

    response = _me_with_session_cookie(auth_client, expired_token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_wrong_secret_session_cookie_returns_401(auth_client) -> None:
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "exp": _future_exp()},
        _OTHER_JWT_SECRET,
        algorithm="HS256",
    )

    response = _me_with_session_cookie(auth_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_alg_none_session_cookie_returns_401(auth_client) -> None:
    user_id = uuid4()
    token = jwt.encode(
        {"sub": str(user_id), "exp": _future_exp()},
        "",
        algorithm="none",
    )

    response = _me_with_session_cookie(auth_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_valid_token_for_deleted_user_returns_401(
    auth_client, db_engine
) -> None:
    register = auth_client.post(
        "/api/auth/register",
        json={"email": "deleted@example.com", "password": "password123"},
    )
    assert register.status_code == 201
    token = register.cookies[SESSION_COOKIE_NAME]

    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM users"))

    response = _me_with_session_cookie(auth_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_with_future_nbf_session_cookie_returns_401_non_blocking(
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

    response = _me_with_session_cookie(auth_client, token)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_login_cookie_is_httponly(auth_client) -> None:
    set_cookie = _login_and_get_set_cookie(auth_client)

    assert "HttpOnly" in set_cookie


def test_login_cookie_samesite_is_lax(auth_client) -> None:
    set_cookie = _login_and_get_set_cookie(auth_client)

    assert "SameSite=lax" in set_cookie


def test_login_cookie_max_age_is_86400(auth_client) -> None:
    set_cookie = _login_and_get_set_cookie(auth_client)

    assert "Max-Age=86400" in set_cookie


def test_login_cookie_includes_secure_when_configured(postgres_url) -> None:
    settings = Settings(
        database_url=postgres_url,
        jwt_secret=_JWT_SECRET,
        cors_origins=["http://testserver"],
        cookie_secure=True,
        cookie_path="/api",
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        client.post(
            "/api/auth/register",
            json={"email": "secure-cookie@example.com", "password": "password123"},
        )
        response = client.post(
            "/api/auth/login",
            json={"email": "secure-cookie@example.com", "password": "password123"},
        )

    assert response.status_code == 200
    assert "Secure" in _set_cookie_header(response)


def test_login_with_nonexistent_email_returns_same_401_as_wrong_password(
    auth_client,
) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

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


def test_register_with_empty_password_returns_422(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "empty@example.com", "password": ""},
    )

    assert response.status_code == 422


def test_register_accessible_without_session_cookie(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "public-register@example.com", "password": "password123"},
    )

    assert response.status_code == 201


def test_login_accessible_without_session_cookie(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "public-login@example.com", "password": "password123"},
    )
    auth_client.cookies.clear()

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "public-login@example.com", "password": "password123"},
    )

    assert response.status_code == 200


def test_health_endpoints_accessible_without_session_cookie(auth_client) -> None:
    assert auth_client.get("/health").status_code == 200
    assert auth_client.get("/api/health").status_code == 200


def test_register_persists_user_registered_event(auth_client, db_engine) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

    with db_engine.connect() as connection:
        result = connection.execute(
            text("SELECT event_type FROM events WHERE event_type = 'UserRegistered'")
        )
        rows = result.fetchall()

    assert len(rows) == 1


def test_register_persists_users_projection_row(auth_client, db_engine) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "password": "password123"},
    )

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
