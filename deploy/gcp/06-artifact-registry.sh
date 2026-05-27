#!/usr/bin/env bash
# Docker Artifact Registry repository for frontend image deploys.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud
gcp_set_project

AR_HOST="${GCP_REGION}-docker.pkg.dev"
IMAGE_PREFIX="${AR_HOST}/${GCP_PROJECT_ID}/${GCP_ARTIFACT_REPO}"

if ! gcloud artifacts repositories describe "${GCP_ARTIFACT_REPO}" \
	--location="${GCP_REGION}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating Artifact Registry repository ${GCP_ARTIFACT_REPO} in ${GCP_REGION}"
	gcloud artifacts repositories create "${GCP_ARTIFACT_REPO}" \
		--project="${GCP_PROJECT_ID}" \
		--repository-format=docker \
		--location="${GCP_REGION}" \
		--description="ADR Flow container images"
else
	gcp_info "Repository ${GCP_ARTIFACT_REPO} already exists"
fi

gcp_save_bootstrap_state "GCP_ARTIFACT_REPO" "${GCP_ARTIFACT_REPO}"
gcp_save_bootstrap_state "AR_IMAGE_PREFIX" "${IMAGE_PREFIX}"

cat <<EOF

Artifact Registry ready.

  Configure Docker auth (once per devcontainer):
    gcloud auth configure-docker ${AR_HOST} --quiet

  Example web image:
    ${IMAGE_PREFIX}/adr-flow-web:latest

Bootstrap complete. See ${SCRIPT_DIR}/README.md for deploy and verification steps.
EOF
