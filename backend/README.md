# ADR Flow API (FastAPI + uv)

## Local development

```bash
uv run uvicorn main:app --reload
# or from repo root: just dev-backend
```

Local dev serves on port **8000** (`main()` in `main.py`). Cloud Run uses the Python buildpack default (**8080**).

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
