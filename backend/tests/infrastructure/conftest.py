"""Shared fixtures for infrastructure integration tests."""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from infrastructure.adapters.persistence.database_url import normalize_database_url


def _resolve_test_database_url() -> str | None:
    raw = os.environ.get("TEST_DATABASE_URL")
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
    url = _resolve_test_database_url()
    if url is None:
        pytest.skip("TEST_DATABASE_URL is not set")
    if not _can_connect(url):
        pytest.fail(
            "Postgres is unavailable at TEST_DATABASE_URL. "
            "Run post-create hooks or set a reachable test database URL."
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
