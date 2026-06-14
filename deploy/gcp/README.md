# GCP bootstrap scripts

Versioned one-time provisioning for the **MVP single project** (`adr-flow` by default) in **`europe-west1`**.

**Operator runbook** (environments, auth, CI, rollback, troubleshooting): [`context/foundation/deploy-gcp.md`](../../context/foundation/deploy-gcp.md).

**Platform decision** (why GCP, risks): [`context/foundation/infrastructure.md`](../../context/foundation/infrastructure.md).

## Quick start

1. Devcontainer: `just gcp-auth` → `just gcp-auth-login` (see runbook).
2. `cp secrets.env.example secrets.env` and set `GCP_BILLING_ACCOUNT`, `OPENROUTER_API_KEY`.
3. Run scripts `01`–`06` below.
4. `just gcp-deploy-api` then `just gcp-deploy-web`.
5. Configure GitHub Actions variables after `05` (see runbook).

Optional root `.env`: `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_ZONE`, `GITHUB_REPO`.

## Run order

```bash
cd deploy/gcp
cp secrets.env.example secrets.env   # edit before running

./01-project-apis.sh
./02-network.sh
./03-gce-postgres.sh
./04-secrets.sh
./05-wif-github.sh
./06-artifact-registry.sh
```

## What each script creates

| Script | Resources |
|--------|-----------|
| `01-project-apis.sh` | Project `adr-flow`, billing link, Run/Compute/Secret Manager/Build/AR/IAM/Storage APIs |
| `02-network.sh` | Subnet `adr-flow-cloud-run` (`10.8.0.0/24`), firewall `allow-cloud-run-to-postgres` (5432 from subnet only) |
| `03-gce-postgres.sh` | VM `adr-flow-db`, bucket `gs://adr-flow-backups-eu`, daily `pg_dump` cron |
| `04-secrets.sh` | Secrets `db-url`, `openrouter-key`; SA `adr-flow-api-run` |
| `05-wif-github.sh` | WIF pool/provider, SA `adr-flow-github-deploy`, repo condition `web-lizzard/adr-flow` |
| `06-artifact-registry.sh` | Docker repo `adr-flow` in `europe-west1` |

## Networking

- Postgres firewall: **only** Cloud Run egress subnet `10.8.0.0/24` (not `0.0.0.0/0`).
- API deploy: `--network=default --subnet=adr-flow-cloud-run --vpc-egress=private-ranges-only`.
- `DATABASE_URL`: GCE **internal** IP — `postgresql+asyncpg://adrflow:PASSWORD@10.x.x.x:5432/adrflow`.

## Postgres VM (`postgres-vm-setup.sh`)

- `listen_addresses = '*'`, `pg_hba.conf` `scram-sha-256` for `10.8.0.0/24`, `max_connections = 20`
- Admin: `gcloud compute ssh adr-flow-db --zone=europe-west1-b`

## Gitignored

- `secrets.env`, `.bootstrap-state.env`, optional `dev-sa.json` (MVP only; never for CI)

## Deploy commands

| Command | When | Notes |
|---------|------|-------|
| `just gcp-migrate-api` | After `04-secrets.sh` | `deploy-migrate-api.sh` + [`run-migrate-api.flags`](run-migrate-api.flags) |
| `just gcp-deploy-api` | After `04-secrets.sh` | `deploy-api.sh` + [`run-api.flags`](run-api.flags) |
| `just gcp-deploy-web` | After `06` + API live | `deploy-web.sh` + [`run-web.flags`](run-web.flags); sets `NUXT_API_UPSTREAM` |

**API** (`adr-flow-api`): `--source backend`, `GOOGLE_PYTHON_PACKAGE_MANAGER=uv`, secrets via `run-api.flags`.

**Web** (`adr-flow-web`): `gcloud builds submit` on `frontend/`, image to Artifact Registry, `NUXT_API_UPSTREAM` from API URL. No VPC on web.

Verify:

```bash
curl "$(gcloud run services describe adr-flow-api --region=europe-west1 --format='value(status.url)')/health"
curl "$(gcloud run services describe adr-flow-web --region=europe-west1 --format='value(status.url)')/api/health"
```

## Database migrations

Production Postgres runs on a GCE VM with a private IP. The firewall only allows connections from the Cloud Run subnet `10.8.0.0/24` — GitHub-hosted runners **cannot** connect directly.

### PR CI

[`backend-ci.yml`](../../.github/workflows/backend-ci.yml) runs on every pull request touching `backend/`. It spins up an ephemeral `postgres:15-alpine` service container (matching the production PG version) and validates:

- `alembic upgrade head` applies cleanly on a fresh database
- `alembic current --check-heads` confirms the head revision
- `alembic check` catches metadata drift against `models.py`
- Persistence and domain tests pass
- Ruff lint and ty type checks pass

No GCP auth, secrets, or VPC access needed — fully self-contained.

### Production

[`deploy-gcp.yml`](../../.github/workflows/deploy-gcp.yml) runs the `migrate-api` job before `deploy-api` on every merge to `main` that touches backend files. The job calls [`deploy-migrate-api.sh`](deploy-migrate-api.sh) which:

1. Deploys (or updates) a stable Cloud Run Job `adr-flow-api-migrate` from `backend/` source
2. Executes it synchronously (`--wait`)
3. The job runs `alembic upgrade head` (Alembic console script from the buildpack venv) against `DATABASE_URL` from Secret Manager (`db-url:latest`)

The migration job uses the same service account (`adr-flow-api-run`), VPC egress, network, and subnet as the API service. Flags live in [`run-migrate-api.flags`](run-migrate-api.flags).

**Build note**: `gcloud run jobs deploy --source` does not accept `--set-build-env-vars` (unlike `gcloud run deploy` for services). The uv buildpack activates automatically when `backend/pyproject.toml` and `backend/uv.lock` are present. At runtime the job uses the buildpack `launcher` entrypoint with `python -m alembic upgrade head` — overriding `--command` to `uv` or `alembic` directly fails because those binaries are not on PATH outside the launcher.

**Alembic URL normalization**: the `DATABASE_URL` secret stores `postgresql+asyncpg://…` for the async API runtime. Alembic's `env.py` normalizes this to the sync `psycopg` driver at load time.

### Operations

| Task | Command |
|------|---------|
| Manual migration (production) | `just gcp-migrate-api` |
| List recent executions | `gcloud run jobs executions list --job=adr-flow-api-migrate --region=europe-west1` |
| Read execution logs | `gcloud logging read 'resource.labels.job_name="adr-flow-api-migrate"' --project=adr-flow --limit=50` |

**Failure handling**: fix the migration, push to `main`, and let CI re-run the job. Do not deploy the API until migration succeeds — the workflow enforces this (`deploy-api` depends on `migrate-api`). Schema rollback is not automatic with Cloud Run revision rollback; prefer forward-compatible migrations.

**Connection budget**: the VM has `max_connections = 20`. The migration job runs a single task — no connection pool needed. Workflow-level concurrency (`cancel-in-progress: false`) prevents parallel migration jobs.

### First-time bootstrap

If GCP scripts `01`–`06` have not been run, `migrate-api` will fail at auth or missing SA. Complete the bootstrap first (see Quick start above).

CI uses the same scripts/flags: [deploy-gcp.yml](../../.github/workflows/deploy-gcp.yml) (migrations, then API, then web when both change).
