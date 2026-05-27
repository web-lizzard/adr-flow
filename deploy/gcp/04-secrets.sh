#!/usr/bin/env bash
# Secret Manager: db-url, openrouter-key; API Cloud Run runtime service account.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud
gcp_set_project

secret_upsert() {
	local name="$1"
	local value="$2"
	if gcloud secrets describe "${name}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
		printf '%s' "${value}" | gcloud secrets versions add "${name}" \
			--project="${GCP_PROJECT_ID}" \
			--data-file=-
	else
		printf '%s' "${value}" | gcloud secrets create "${name}" \
			--project="${GCP_PROJECT_ID}" \
			--replication-policy=automatic \
			--data-file=-
	fi
}

# Resolve DATABASE_URL from bootstrap state or live GCE metadata.
if [[ -z "${DATABASE_URL:-}" ]]; then
	if [[ -n "${DB_INTERNAL_IP:-}" && -n "${POSTGRES_PASSWORD:-}" ]]; then
		DATABASE_URL="postgresql+asyncpg://${DB_USER}:${POSTGRES_PASSWORD}@${DB_INTERNAL_IP}:5432/${DB_NAME}"
	elif gcloud compute instances describe "${GCE_INSTANCE}" \
		--zone="${GCP_ZONE}" \
		--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
		if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
			echo "error: POSTGRES_PASSWORD required (set in secrets.env or re-run 03-gce-postgres.sh)" >&2
			exit 1
		fi
		DB_INTERNAL_IP="$(gcloud compute instances describe "${GCE_INSTANCE}" \
			--zone="${GCP_ZONE}" \
			--project="${GCP_PROJECT_ID}" \
			--format='get(networkInterfaces[0].networkIP)')"
		DATABASE_URL="postgresql+asyncpg://${DB_USER}:${POSTGRES_PASSWORD}@${DB_INTERNAL_IP}:5432/${DB_NAME}"
	else
		echo "error: run 03-gce-postgres.sh first or set DATABASE_URL in secrets.env" >&2
		exit 1
	fi
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
	echo "error: OPENROUTER_API_KEY required in deploy/gcp/secrets.env" >&2
	exit 1
fi

gcp_info "Creating/updating Secret Manager secrets"
secret_upsert "db-url" "${DATABASE_URL}"
secret_upsert "openrouter-key" "${OPENROUTER_API_KEY}"

API_RUN_SA_EMAIL="${API_RUN_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "${API_RUN_SA_EMAIL}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating API Cloud Run service account ${API_RUN_SA_NAME}"
	gcloud iam service-accounts create "${API_RUN_SA_NAME}" \
		--project="${GCP_PROJECT_ID}" \
		--display-name="ADR Flow API (Cloud Run runtime)"
fi

for secret_id in db-url openrouter-key; do
	gcloud secrets add-iam-policy-binding "${secret_id}" \
		--project="${GCP_PROJECT_ID}" \
		--member="serviceAccount:${API_RUN_SA_EMAIL}" \
		--role="roles/secretmanager.secretAccessor" \
		--quiet >/dev/null
done

gcp_save_bootstrap_state "API_RUN_SA_EMAIL" "${API_RUN_SA_EMAIL}"

gcp_info "Secrets ready. API deploy: --service-account=${API_RUN_SA_EMAIL} --set-secrets=DATABASE_URL=db-url:latest,OPENROUTER_API_KEY=openrouter-key:latest"
gcp_info "Next: ${SCRIPT_DIR}/05-wif-github.sh"
