"""Bearer transport contract tests for Phase 1 auth migration."""

from infrastructure.config import Settings


def _bearer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_access_token_without_set_cookie(auth_client) -> None:
    response = auth_client.post(
        "/api/auth/register",
        json={"email": "bearer@example.com", "password": "password123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {"access_token": body["access_token"]}
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "set-cookie" not in response.headers


def test_login_returns_access_token_without_set_cookie(auth_client) -> None:
    auth_client.post(
        "/api/auth/register",
        json={"email": "bearer-login@example.com", "password": "password123"},
    )

    response = auth_client.post(
        "/api/auth/login",
        json={"email": "bearer-login@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"access_token": body["access_token"]}
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "set-cookie" not in response.headers


def test_me_with_valid_bearer_token_returns_200(auth_client) -> None:
    register = auth_client.post(
        "/api/auth/register",
        json={"email": "bearer-me@example.com", "password": "password123"},
    )
    assert register.status_code == 201
    token = register.json()["access_token"]

    response = auth_client.get("/api/auth/me", headers=_bearer_headers(token))

    assert response.status_code == 200
    assert response.json()["email"] == "bearer-me@example.com"


def test_me_without_authorization_header_returns_401(auth_client) -> None:
    response = auth_client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_settings_loads_without_cookie_env_vars(postgres_url, monkeypatch) -> None:
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("COOKIE_PATH", raising=False)

    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
    )

    assert settings.jwt_secret == "test-jwt-secret-at-least-32-characters"
    assert "cookie_secure" not in Settings.model_fields
    assert "cookie_path" not in Settings.model_fields
