"""Auth API integration tests."""

from fastapi.testclient import TestClient
from sqlalchemy import text

from infrastructure.api.dependencies import SESSION_COOKIE_NAME
from infrastructure.bootstrap import create_app
from infrastructure.config import Settings


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
