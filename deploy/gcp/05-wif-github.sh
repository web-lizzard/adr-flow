#!/usr/bin/env bash
# Workload Identity Federation for GitHub Actions (repository-scoped deploy SA).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud
gcp_set_project

PROJECT_NUMBER="$(gcp_project_number)"
DEPLOY_SA_EMAIL="${GITHUB_DEPLOY_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL_ID}"
PROVIDER_RESOURCE="${POOL_RESOURCE}/providers/${WIF_PROVIDER_ID}"
PRINCIPAL_SET="principalSet://iam.googleapis.com/${POOL_RESOURCE}/attribute.repository/${GITHUB_REPO}"

DEPLOY_ROLES=(
	roles/run.admin
	roles/run.sourceDeveloper
	roles/artifactregistry.writer
	roles/cloudbuild.builds.editor
	roles/iam.serviceAccountUser
	roles/secretmanager.secretAccessor
)

if ! gcloud iam workload-identity-pools describe "${WIF_POOL_ID}" \
	--location=global \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating workload identity pool ${WIF_POOL_ID}"
	gcloud iam workload-identity-pools create "${WIF_POOL_ID}" \
		--project="${GCP_PROJECT_ID}" \
		--location=global \
		--display-name="GitHub Actions"
else
	gcp_info "Workload identity pool ${WIF_POOL_ID} already exists"
fi

if ! gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER_ID}" \
	--workload-identity-pool="${WIF_POOL_ID}" \
	--location=global \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating OIDC provider ${WIF_PROVIDER_ID} for ${GITHUB_REPO}"
	gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER_ID}" \
		--project="${GCP_PROJECT_ID}" \
		--location=global \
		--workload-identity-pool="${WIF_POOL_ID}" \
		--display-name="GitHub" \
		--issuer-uri="https://token.actions.githubusercontent.com" \
		--attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
		--attribute-condition="assertion.repository=='${GITHUB_REPO}'"
else
	gcp_info "OIDC provider ${WIF_PROVIDER_ID} already exists"
fi

if ! gcloud iam service-accounts describe "${DEPLOY_SA_EMAIL}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating GitHub deploy service account ${GITHUB_DEPLOY_SA_NAME}"
	gcloud iam service-accounts create "${GITHUB_DEPLOY_SA_NAME}" \
		--project="${GCP_PROJECT_ID}" \
		--display-name="ADR Flow GitHub Actions deploy"
fi

for role in "${DEPLOY_ROLES[@]}"; do
	gcp_info "Granting ${role} to ${GITHUB_DEPLOY_SA_NAME}"
	gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
		--member="serviceAccount:${DEPLOY_SA_EMAIL}" \
		--role="${role}" \
		--quiet >/dev/null
done

gcp_info "Binding WIF principal to deploy SA (repository=${GITHUB_REPO})"
gcloud iam service-accounts add-iam-policy-binding "${DEPLOY_SA_EMAIL}" \
	--project="${GCP_PROJECT_ID}" \
	--role="roles/iam.workloadIdentityUser" \
	--member="${PRINCIPAL_SET}" \
	--quiet >/dev/null

# Allow GitHub deploy SA to act as API runtime SA when deploying Cloud Run.
if [[ -n "${API_RUN_SA_EMAIL:-}" ]] || gcloud iam service-accounts describe \
	"${API_RUN_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	API_RUN_SA_EMAIL="${API_RUN_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
	gcloud iam service-accounts add-iam-policy-binding "${API_RUN_SA_EMAIL}" \
		--project="${GCP_PROJECT_ID}" \
		--role="roles/iam.serviceAccountUser" \
		--member="serviceAccount:${DEPLOY_SA_EMAIL}" \
		--quiet >/dev/null
fi

# Cloud Run --source uploads to run-sources-PROJECT-REGION (created on first API deploy).
# Project roles alone may not satisfy buckets.get on that bucket; grant bucket IAM when it exists.
RUN_SOURCES_BUCKET="run-sources-${GCP_PROJECT_ID}-${GCP_REGION}"
if gcloud storage buckets describe "gs://${RUN_SOURCES_BUCKET}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Granting storage.admin on gs://${RUN_SOURCES_BUCKET} for GitHub API source deploy"
	gcloud storage buckets add-iam-policy-binding "gs://${RUN_SOURCES_BUCKET}" \
		--member="serviceAccount:${DEPLOY_SA_EMAIL}" \
		--role="roles/storage.admin" \
		--quiet >/dev/null
fi

gcp_save_bootstrap_state "WIF_PROVIDER" "${PROVIDER_RESOURCE}"
gcp_save_bootstrap_state "WIF_SERVICE_ACCOUNT" "${DEPLOY_SA_EMAIL}"

cat <<EOF

GitHub Actions configuration (repo → Settings → Secrets and variables → Actions):

  Variables:
    GCP_PROJECT_ID=${GCP_PROJECT_ID}
    GCP_REGION=${GCP_REGION}
    WIF_PROVIDER=${PROVIDER_RESOURCE}
    WIF_SERVICE_ACCOUNT=${DEPLOY_SA_EMAIL}

  Workflow permissions: id-token: write

Next: ${SCRIPT_DIR}/06-artifact-registry.sh
EOF
