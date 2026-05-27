# GCP bootstrap (ADR Flow MVP)

One-time scripts to provision the **single MVP project** (`adr-flow` by default) in **`europe-west1`**. Run from the devcontainer after `gcloud auth login` (credentials live in the `gcloud-config` Docker volume — not a host bind mount).

## Prerequisites

- Google account with billing enabled
- IAM sufficient to create/link project resources (see [infrastructure.md](../../context/foundation/infrastructure.md))
- **`gcloud` CLI in the devcontainer** (see below)
- Copy `secrets.env.example` → `secrets.env` and set `GCP_BILLING_ACCOUNT`, `OPENROUTER_API_KEY`

Optional root `.env` overrides: `GCP_PROJECT_ID`, `GCP_REGION`, `GCP_ZONE`, `GITHUB_REPO`.

### Install `gcloud` and log in (first time)

Credentials are stored in the Docker named volume `gcloud-config` (not a bind mount from the host).

1. **Install CLI** — pick one:
   - **Rebuild** the devcontainer (runs `post-create.d/15-gcloud-cli.sh` automatically), or
   - **Once without rebuild:** `bash .devcontainer/post-create.d/15-gcloud-cli.sh`
2. **Check / log in:**
   ```bash
   just gcp-auth
   just gcp-auth-login    # or: gcloud auth login --no-launch-browser
   ```
   Login needs only a Google account; no GCP project yet.
3. After `01-project-apis.sh` creates the project:
   ```bash
   gcloud config set project adr-flow
   gcloud config set run/region europe-west1
   ```

## Run order

```bash
cd deploy/gcp
cp secrets.env.example secrets.env   # edit before running

./01-project-apis.sh      # project + APIs
./02-network.sh           # Cloud Run subnet 10.8.0.0/24 + Postgres firewall
./03-gce-postgres.sh      # e2-micro VM, Postgres 15, backups bucket
./04-secrets.sh           # Secret Manager + API runtime SA
./05-wif-github.sh        # GitHub Actions WIF + deploy SA
./06-artifact-registry.sh # Docker repo for Nuxt image deploys
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

## Networking (improvements over infra doc)

- **Do not** use `0.0.0.0/0` on the Postgres firewall — only the Cloud Run egress subnet (`10.8.0.0/24`).
- Cloud Run API deploy: `--network=default --subnet=adr-flow-cloud-run --vpc-egress=private-ranges-only`.
- `DATABASE_URL` uses the GCE **internal** IP: `postgresql+asyncpg://adrflow:PASSWORD@10.x.x.x:5432/adrflow`.

## Postgres on the VM

Startup script `postgres-vm-setup.sh` configures:

- `listen_addresses = '*'`
- `pg_hba.conf`: `scram-sha-256` for `10.8.0.0/24` only
- `max_connections = 20` (tune app pool when DB code lands)

Admin access: `gcloud compute ssh adr-flow-db --zone=europe-west1-b`. Postgres is not exposed to the public internet via firewall rules.

## Backups

- Bucket: `gs://adr-flow-backups-eu`
- Cron: daily `pg_dump -Fc` at 03:00 UTC
- Verify weekly: `gsutil ls gs://adr-flow-backups-eu/`

## Gitignored files

- `secrets.env` — billing account, API keys, optional `POSTGRES_PASSWORD`
- `.bootstrap-state.env` — written by scripts (IPs, WIF names, generated passwords)
- `dev-sa.json` — optional headless SA key (MVP project only; never for CI)

## Deploy API (Cloud Run source + uv)

After bootstrap through `04-secrets.sh`, deploy the FastAPI service from `backend/`:

```bash
just gcp-deploy-api
# equivalent: bash deploy/gcp/deploy-api.sh
```

| Input | Role |
|-------|------|
| [`backend/pyproject.toml`](../../backend/pyproject.toml) + [`backend/uv.lock`](../../backend/uv.lock) | Locked dependencies (uv) |
| [`backend/.gcloudignore`](../../backend/.gcloudignore) | Excludes `.venv/`, tests, caches from upload |
| `GOOGLE_PYTHON_PACKAGE_MANAGER=uv` | Buildpack uses uv ([Python on Cloud Run](https://cloud.google.com/run/docs/runtimes/python-dependencies)) |
| [`run-api.flags`](run-api.flags) | Service flags shared with docs / future GHA |

**Service:** `adr-flow-api` in `europe-west1` (override via `.env`: `GCP_PROJECT_ID`, `GCP_REGION`).

**Build:**

```bash
gcloud run deploy adr-flow-api --source backend \
  --set-build-env-vars=GOOGLE_PYTHON_PACKAGE_MANAGER=uv \
  ...
```

The buildpack runs `uvicorn main:app --host 0.0.0.0 --port 8080` when `uvicorn` is in project dependencies.

**Runtime flags** ([`run-api.flags`](run-api.flags)):

| Flag | Value | Why |
|------|-------|-----|
| `--min-instances` | `0` | Scale to zero |
| `--max-instances` | `1` | MVP single-instance dispatch |
| `--no-cpu-throttling` | on | Background asyncio after response |
| `--cpu-boost` | on | Cold start |
| `--vpc-egress` | `private-ranges-only` | Reach GCE Postgres private IP |
| `--network` / `--subnet` | `default` / `adr-flow-cloud-run` | Direct VPC egress |
| `--set-secrets` | `DATABASE_URL=db-url:latest`, `OPENROUTER_API_KEY=openrouter-key:latest` | Secret Manager |
| `--service-account` | `adr-flow-api-run@…` | Set by `deploy-api.sh` from bootstrap state |

Verify: `curl "$(gcloud run services describe adr-flow-api --region=europe-west1 --format='value(status.url)')/health"` → `{"status":"ok"}`.

**Note:** With `--min-instances=0`, instances can scale down after idle even with `--no-cpu-throttling`. Long background jobs may need `--min-instances=1` temporarily (cost trade-off).

## Phase 2 — production (deferred)

When adding `adr-flow-prod`: new project, GitHub Environment `production`, `workflow_dispatch` deploy, **no** prod deploy from this devcontainer. See `docs/deploy/gcp.md` when added.
