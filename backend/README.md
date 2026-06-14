# ADR Flow API (FastAPI + uv)

## Local development

```bash
uv run uvicorn main:app --reload
# or from repo root: just dev-backend
```

Local dev serves on port **8000** (`main()` in `main.py`). Cloud Run uses the Python buildpack default (**8080**).

## Database migrations

Schema changes are managed with Alembic under `infrastructure/adapters/persistence/migrations/`. ORM table metadata lives in `infrastructure/adapters/persistence/models.py`.

In the devcontainer, point `DATABASE_URL` at the bundled Postgres service:

```text
postgresql://postgres:postgres@postgres:5432/adr_flow
```

From the repository root:

```bash
just migrate-backend          # apply pending migrations (alembic upgrade head)
just migrate-backend-current  # show current revision
just migrate-backend-history  # list revision history
```

Run the same commands from `backend/` with `uv run alembic …` if you prefer. Alembic reads `DATABASE_URL` at execution time and normalizes `postgresql+asyncpg://` URLs to the sync `psycopg` driver.

Migration commands only evolve the database schema. The FastAPI app does not run migrations on startup — apply migrations explicitly before relying on new tables locally or in deploy pipelines.

### CI and production

- **PR validation**: [`.github/workflows/backend-ci.yml`](../.github/workflows/backend-ci.yml) runs migrations against an ephemeral Postgres 15 service on every pull request touching `backend/`. The devcontainer uses Postgres 16 for day-to-day work; CI uses 15 for production parity.
- **Production migrations**: `just gcp-migrate-api` deploys and executes a Cloud Run Job (`adr-flow-api-migrate`) that runs `alembic upgrade head` inside the VPC. This runs automatically before API deploy in CI.
- **Networking rationale**: see [`deploy/gcp/README.md`](../deploy/gcp/README.md#database-migrations) for why migrations run from GCP rather than GitHub runners.

## Cloud Run (source deploy)

Deploy from the **repository root** after GCP bootstrap (`deploy/gcp/01-…` through `04-secrets.sh`):

```bash
just gcp-deploy-api
# or: bash deploy/gcp/deploy-api.sh
```

Build context is `backend/` (respects [`backend/.gcloudignore`](.gcloudignore)). Cloud Build uses **uv** via:

`--set-build-env-vars=GOOGLE_PYTHON_PACKAGE_MANAGER=uv`

Dependencies come from [`pyproject.toml`](pyproject.toml) and [`uv.lock`](uv.lock) — keep `uv.lock` committed; do not add a committed `requirements.txt` for deploy.

Runtime flags (VPC egress to GCE Postgres, secrets, scaling) live in [`deploy/gcp/run-api.flags`](../deploy/gcp/run-api.flags). See [`deploy/gcp/README.md`](../deploy/gcp/README.md) for the full command and troubleshooting.

Manual one-liner (after `gcloud auth login` and bootstrap):

```bash
gcloud run deploy adr-flow-api --source backend \
  --project="${GCP_PROJECT_ID:-adr-flow}" \
  --set-build-env-vars=GOOGLE_PYTHON_PACKAGE_MANAGER=uv \
  $(grep -v '^#' deploy/gcp/run-api.flags | xargs) \
  --service-account=adr-flow-api-run@${GCP_PROJECT_ID:-adr-flow}.iam.gserviceaccount.com
```

Smoke test: `curl "$(gcloud run services describe adr-flow-api --region=europe-west1 --format='value(status.url)')/health"`
