"""Shared fixtures for auth API integration tests."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from infrastructure.adapters.persistence.database_url import normalize_database_url
from infrastructure.bootstrap import create_app
from infrastructure.config import Settings


def _resolve_database_url() -> str | None:
    raw = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not raw:
        return None
    return normalize_database_url(raw)


def _can_connect(url: str) -> bool:
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": "-c client_encoding=UTF8"},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    finally:
        engine.dispose()
    return True


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = _resolve_database_url()
    if url is None:
        pytest.skip("DATABASE_URL or TEST_DATABASE_URL is not set")
    if not _can_connect(url):
        pytest.fail(
            "Postgres is unavailable at DATABASE_URL/TEST_DATABASE_URL. "
            "Start the devcontainer postgres service or set a reachable test URL."
        )
    return url


@pytest.fixture()
def db_engine(postgres_url: str) -> Iterator[Engine]:
    engine = create_engine(
        postgres_url,
        pool_pre_ping=True,
        connect_args={"options": "-c client_encoding=UTF8"},
    )
    yield engine
    engine.dispose()


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
        cookie_secure=False,
    )
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client
