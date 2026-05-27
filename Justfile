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

# --- GCP (devcontainer; MVP project only) — logic in scripts/gcp/ ---

gcp-auth:
    @bash scripts/gcp/auth.sh

gcp-auth-login:
    @bash scripts/gcp/auth-login.sh

gcp-deploy-api:
    @bash deploy/gcp/deploy-api.sh
