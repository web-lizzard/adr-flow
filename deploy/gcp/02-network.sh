#!/usr/bin/env bash
# Dedicated subnet for Cloud Run Direct VPC egress + Postgres firewall (10.8.0.0/24 only).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud
gcp_set_project

FIREWALL_RULE="allow-cloud-run-to-postgres"

if ! gcloud compute networks subnets describe "${CLOUD_RUN_SUBNET}" \
	--region="${GCP_REGION}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating subnet ${CLOUD_RUN_SUBNET} (${CLOUD_RUN_SUBNET_RANGE}) in ${VPC_NETWORK}"
	gcloud compute networks subnets create "${CLOUD_RUN_SUBNET}" \
		--project="${GCP_PROJECT_ID}" \
		--network="${VPC_NETWORK}" \
		--region="${GCP_REGION}" \
		--range="${CLOUD_RUN_SUBNET_RANGE}"
else
	gcp_info "Subnet ${CLOUD_RUN_SUBNET} already exists"
fi

if ! gcloud compute firewall-rules describe "${FIREWALL_RULE}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating firewall ${FIREWALL_RULE} (tcp:5432 from ${CLOUD_RUN_SUBNET_RANGE} only)"
	gcloud compute firewall-rules create "${FIREWALL_RULE}" \
		--project="${GCP_PROJECT_ID}" \
		--network="${VPC_NETWORK}" \
		--direction=INGRESS \
		--action=ALLOW \
		--rules=tcp:5432 \
		--source-ranges="${CLOUD_RUN_SUBNET_RANGE}" \
		--target-tags=postgres
else
	gcp_info "Updating firewall ${FIREWALL_RULE} source range to ${CLOUD_RUN_SUBNET_RANGE}"
	gcloud compute firewall-rules update "${FIREWALL_RULE}" \
		--project="${GCP_PROJECT_ID}" \
		--source-ranges="${CLOUD_RUN_SUBNET_RANGE}"
fi

gcp_save_bootstrap_state "CLOUD_RUN_SUBNET" "${CLOUD_RUN_SUBNET}"
gcp_save_bootstrap_state "CLOUD_RUN_SUBNET_RANGE" "${CLOUD_RUN_SUBNET_RANGE}"

gcp_info "Network ready. Cloud Run deploy flags: --network=${VPC_NETWORK} --subnet=${CLOUD_RUN_SUBNET} --vpc-egress=private-ranges-only"
gcp_info "Next: ${SCRIPT_DIR}/03-gce-postgres.sh"
