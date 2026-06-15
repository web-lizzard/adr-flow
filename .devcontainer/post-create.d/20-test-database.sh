#!/usr/bin/env bash
# Create adr_flow_test and apply migrations for integration tests.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@postgres:5432/adr_flow}"
TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql://postgres:postgres@postgres:5432/adr_flow_test}"
TEST_DB_NAME="${TEST_DATABASE_URL##*/}"

echo "Ensuring test database exists: ${TEST_DB_NAME} ..."
cd "${WORKSPACE_ROOT}/backend"
uv run python - "${DATABASE_URL}" "${TEST_DB_NAME}" <<'PY'
import sys

from sqlalchemy import create_engine, text

from infrastructure.adapters.persistence.database_url import normalize_database_url

admin_url = normalize_database_url(sys.argv[1])
test_db_name = sys.argv[2]
engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
with engine.connect() as connection:
    exists = connection.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :name"),
        {"name": test_db_name},
    ).scalar()
    if not exists:
        connection.execute(text(f'CREATE DATABASE "{test_db_name}"'))
engine.dispose()
PY

echo "Applying migrations to test database ..."
DATABASE_URL="${TEST_DATABASE_URL}" uv run alembic upgrade head

echo "Test database ready at ${TEST_DATABASE_URL}."
