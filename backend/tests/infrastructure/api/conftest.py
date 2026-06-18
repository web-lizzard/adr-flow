"""Fixtures for auth API integration tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from infrastructure.bootstrap import create_app
from infrastructure.config import Settings


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
        cookie_secure=False,
        cookie_path="/api",
        llm_provider="fake",
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client
