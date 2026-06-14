"""Database URL helpers for persistence adapters."""


def normalize_database_url(url: str) -> str:
    """Map async or bare Postgres URLs to the sync psycopg driver for Alembic."""
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql+asyncpg://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url
