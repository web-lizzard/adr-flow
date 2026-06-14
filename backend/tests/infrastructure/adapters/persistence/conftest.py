"""Shared fixtures for persistence adapter tests."""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from infrastructure.adapters.persistence.database_url import normalize_database_url


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
