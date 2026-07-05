"""Fixtures for auth API integration tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from infrastructure.bootstrap import create_app
from infrastructure.config import Settings


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_and_get_token(
    client: TestClient,
    email: str,
    *,
    password: str = "password123",
) -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def login_and_get_token(
    client: TestClient,
    email: str,
    *,
    password: str = "password123",
) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def set_bearer_auth(client: TestClient, token: str) -> None:
    client.headers["Authorization"] = f"Bearer {token}"


def clear_bearer_auth(client: TestClient) -> None:
    client.headers.pop("Authorization", None)


@pytest.fixture(autouse=True)
def clean_auth_tables(db_engine: Engine) -> None:
    with db_engine.begin() as connection:
        connection.execute(text("DELETE FROM adrs"))
        connection.execute(text("DELETE FROM users"))
        connection.execute(text("DELETE FROM events"))


@pytest.fixture()
def auth_client(postgres_url: str) -> Iterator[TestClient]:
    settings = Settings(
        database_url=postgres_url,
        jwt_secret="test-jwt-secret-at-least-32-characters",
        cors_origins=["http://testserver"],
        llm_provider="fake",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client
