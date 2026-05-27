#!/usr/bin/env bash
# Create GCP project (optional), link billing, enable APIs for ADR Flow MVP.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud

APIS=(
	run.googleapis.com
	compute.googleapis.com
	secretmanager.googleapis.com
	cloudbuild.googleapis.com
	artifactregistry.googleapis.com
	iam.googleapis.com
	iamcredentials.googleapis.com
	sts.googleapis.com
	cloudresourcemanager.googleapis.com
	storage.googleapis.com
)

if ! gcloud projects describe "${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating project ${GCP_PROJECT_ID}"
	if [[ -z "${GCP_BILLING_ACCOUNT:-}" ]]; then
		echo "error: new project requires GCP_BILLING_ACCOUNT in deploy/gcp/secrets.env" >&2
		echo "  gcloud billing accounts list" >&2
		exit 1
	fi
	gcloud projects create "${GCP_PROJECT_ID}" --name="ADR Flow"
	gcp_info "Linking billing account"
	gcloud billing projects link "${GCP_PROJECT_ID}" \
		--billing-account="${GCP_BILLING_ACCOUNT}"
else
	gcp_info "Project ${GCP_PROJECT_ID} already exists"
	if [[ -n "${GCP_BILLING_ACCOUNT:-}" ]]; then
		if ! gcloud billing projects describe "${GCP_PROJECT_ID}" \
			--format='value(billingAccountName)' 2>/dev/null | grep -q billingAccounts; then
			gcp_info "Linking billing account"
			gcloud billing projects link "${GCP_PROJECT_ID}" \
				--billing-account="${GCP_BILLING_ACCOUNT}"
		fi
	fi
fi

gcp_set_project

gcp_info "Enabling APIs (may take a minute)"
gcloud services enable "${APIS[@]}" --project="${GCP_PROJECT_ID}"

gcp_info "Project ${GCP_PROJECT_ID} ready. Next: ${SCRIPT_DIR}/02-network.sh"
