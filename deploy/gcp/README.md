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
| `just gcp-deploy-api` | After `04-secrets.sh` | `deploy-api.sh` + [`run-api.flags`](run-api.flags) |
| `just gcp-deploy-web` | After `06` + API live | `deploy-web.sh` + [`run-web.flags`](run-web.flags); sets `NUXT_API_UPSTREAM` |

**API** (`adr-flow-api`): `--source backend`, `GOOGLE_PYTHON_PACKAGE_MANAGER=uv`, secrets via `run-api.flags`.

**Web** (`adr-flow-web`): `gcloud builds submit` on `frontend/`, image to Artifact Registry, `NUXT_API_UPSTREAM` from API URL. No VPC on web.

Verify:

```bash
curl "$(gcloud run services describe adr-flow-api --region=europe-west1 --format='value(status.url)')/health"
curl "$(gcloud run services describe adr-flow-web --region=europe-west1 --format='value(status.url)')/api/health"
```

CI uses the same scripts/flags: [deploy-api.yml](../../.github/workflows/deploy-api.yml), [deploy-web.yml](../../.github/workflows/deploy-web.yml).
