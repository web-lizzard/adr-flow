# Dev orchestration — bootstrapper v1
# Install just: https://github.com/casey/just#installation

set shell := ["bash", "-cu"]

# --- bootstrapper dev recipes (v1) ---

dev-frontend:
    cd frontend && pnpm run dev

dev-backend:
    cd backend && uv run uvicorn main:app --reload

dev:
    @just dev-frontend & just dev-backend & wait

test-frontend:
    cd frontend && pnpm run test

test-backend:
    cd backend && uv run pytest

test:
    just test-frontend
    just test-backend

# --- backend migrations (DATABASE_URL from devcontainer or caller env) ---

migrate-backend:
    cd backend && uv run alembic upgrade head

migrate-backend-test:
    cd backend && DATABASE_URL="${TEST_DATABASE_URL:?TEST_DATABASE_URL is not set}" uv run alembic upgrade head

migrate-backend-current:
    cd backend && uv run alembic current

migrate-backend-history:
    cd backend && uv run alembic history

# --- GCP (devcontainer; MVP project only) — logic in scripts/gcp/ ---

gcp-auth:
    @bash scripts/gcp/auth.sh

gcp-auth-login:
    @bash scripts/gcp/auth-login.sh

gcp-migrate-api:
    @bash deploy/gcp/deploy-migrate-api.sh

gcp-deploy-api:
    @bash deploy/gcp/deploy-api.sh

gcp-deploy-web:
    @bash deploy/gcp/deploy-web.sh

# --- MCP (devcontainer diagnostics) ---

mcp-verify:
    @bash scripts/mcp/verify.sh
