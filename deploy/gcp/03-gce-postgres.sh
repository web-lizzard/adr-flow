#!/usr/bin/env bash
# GCE e2-micro Postgres VM, backup bucket, VM service account, startup provisioning.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud
gcp_set_project

if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
	POSTGRES_PASSWORD="$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)"
	gcp_warn "Generated POSTGRES_PASSWORD — add to deploy/gcp/secrets.env before re-running 04-secrets.sh"
	printf 'POSTGRES_PASSWORD=%s\n' "${POSTGRES_PASSWORD}"
fi

VM_SA_EMAIL="${GCE_VM_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
BUCKET_URI="gs://${BACKUP_BUCKET}"

if ! gcloud iam service-accounts describe "${VM_SA_EMAIL}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating VM service account ${GCE_VM_SA_NAME}"
	gcloud iam service-accounts create "${GCE_VM_SA_NAME}" \
		--project="${GCP_PROJECT_ID}" \
		--display-name="ADR Flow Postgres VM"
fi

if ! gcloud storage buckets describe "${BUCKET_URI}" >/dev/null 2>&1; then
	gcp_info "Creating backup bucket ${BUCKET_URI}"
	gcloud storage buckets create "${BUCKET_URI}" \
		--project="${GCP_PROJECT_ID}" \
		--location="${GCP_REGION}" \
		--uniform-bucket-level-access
else
	gcp_info "Backup bucket ${BUCKET_URI} already exists"
fi

gcloud storage buckets add-iam-policy-binding "${BUCKET_URI}" \
	--member="serviceAccount:${VM_SA_EMAIL}" \
	--role="roles/storage.objectCreator" \
	--quiet >/dev/null

STARTUP_SCRIPT="${SCRIPT_DIR}/postgres-vm-setup.sh"
if [[ ! -f "${STARTUP_SCRIPT}" ]]; then
	echo "error: missing ${STARTUP_SCRIPT}" >&2
	exit 1
fi

if ! gcloud compute instances describe "${GCE_INSTANCE}" \
	--zone="${GCP_ZONE}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	gcp_info "Creating GCE instance ${GCE_INSTANCE} (${GCE_MACHINE_TYPE}, ${GCE_DISK_TYPE})"
	gcloud compute instances create "${GCE_INSTANCE}" \
		--project="${GCP_PROJECT_ID}" \
		--zone="${GCP_ZONE}" \
		--machine-type="${GCE_MACHINE_TYPE}" \
		--boot-disk-size="${GCE_DISK_SIZE_GB}GB" \
		--boot-disk-type="${GCE_DISK_TYPE}" \
		--image-family=debian-12 \
		--image-project=debian-cloud \
		--tags=postgres \
		--service-account="${VM_SA_EMAIL}" \
		--scopes=https://www.googleapis.com/auth/cloud-platform \
		--metadata="postgres-password=${POSTGRES_PASSWORD},db-name=${DB_NAME},db-user=${DB_USER},cloud-run-subnet-range=${CLOUD_RUN_SUBNET_RANGE},backup-bucket=${BACKUP_BUCKET},postgres-version=${POSTGRES_VERSION}" \
		--metadata-from-file="startup-script=${STARTUP_SCRIPT}"
else
	gcp_info "Instance ${GCE_INSTANCE} already exists — skipping create (re-run setup via SSH if needed)"
fi

gcp_info "Waiting for Postgres setup on ${GCE_INSTANCE} (check serial log if slow)"
postgres_ready=0
for _ in $(seq 1 36); do
	if gcloud compute ssh "${GCE_INSTANCE}" \
		--zone="${GCP_ZONE}" \
		--project="${GCP_PROJECT_ID}" \
		--quiet \
		--command="test -f /var/lib/adr-flow/postgres-ready" 2>/dev/null; then
		postgres_ready=1
		break
	fi
	sleep 10
done
if [[ "${postgres_ready}" -ne 1 ]]; then
	gcp_warn "Timed out waiting for postgres-ready marker"
	gcp_warn "Inspect: gcloud compute instances get-serial-port-output ${GCE_INSTANCE} --zone=${GCP_ZONE}"
	exit 1
fi

INTERNAL_IP="$(gcloud compute instances describe "${GCE_INSTANCE}" \
	--zone="${GCP_ZONE}" \
	--project="${GCP_PROJECT_ID}" \
	--format='get(networkInterfaces[0].networkIP)')"

DATABASE_URL="postgresql+asyncpg://${DB_USER}:${POSTGRES_PASSWORD}@${INTERNAL_IP}:5432/${DB_NAME}"

gcp_save_bootstrap_state "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD}"
gcp_save_bootstrap_state "DB_INTERNAL_IP" "${INTERNAL_IP}"
gcp_save_bootstrap_state "DATABASE_URL" "${DATABASE_URL}"

gcp_info "Postgres internal IP: ${INTERNAL_IP}"
gcp_info "DATABASE_URL (for Secret Manager): ${DATABASE_URL}"
gcp_info "Next: ${SCRIPT_DIR}/04-secrets.sh"
