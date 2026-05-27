# Shared configuration for deploy/gcp bootstrap scripts.
# shellcheck shell=bash
# Source from sibling scripts: source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

set -euo pipefail

_gcp_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GCP_DEPLOY_DIR="${_gcp_script_dir}"
WORKSPACE_ROOT="$(cd "${GCP_DEPLOY_DIR}/../.." && pwd)"

gcp_apply_defaults() {
	export GCP_PROJECT_ID="${GCP_PROJECT_ID:-adr-flow}"
	export GCP_REGION="${GCP_REGION:-europe-west1}"
	export GCP_ZONE="${GCP_ZONE:-europe-west1-b}"
	export GCP_ARTIFACT_REPO="${GCP_ARTIFACT_REPO:-adr-flow}"
	export GITHUB_REPO="${GITHUB_REPO:-web-lizzard/adr-flow}"

	export VPC_NETWORK="${VPC_NETWORK:-default}"
	export CLOUD_RUN_SUBNET="${CLOUD_RUN_SUBNET:-adr-flow-cloud-run}"
	export CLOUD_RUN_SUBNET_RANGE="${CLOUD_RUN_SUBNET_RANGE:-10.8.0.0/24}"

	export GCE_INSTANCE="${GCE_INSTANCE:-adr-flow-db}"
	export GCE_MACHINE_TYPE="${GCE_MACHINE_TYPE:-e2-micro}"
	export GCE_DISK_SIZE_GB="${GCE_DISK_SIZE_GB:-10}"
	export GCE_DISK_TYPE="${GCE_DISK_TYPE:-pd-ssd}"

	export DB_NAME="${DB_NAME:-adrflow}"
	export DB_USER="${DB_USER:-adrflow}"
	export POSTGRES_VERSION="${POSTGRES_VERSION:-15}"

	export BACKUP_BUCKET="${BACKUP_BUCKET:-adr-flow-backups-eu}"
	export GCE_VM_SA_NAME="${GCE_VM_SA_NAME:-adr-flow-db-vm}"
	export API_RUN_SA_NAME="${API_RUN_SA_NAME:-adr-flow-api-run}"
	export GITHUB_DEPLOY_SA_NAME="${GITHUB_DEPLOY_SA_NAME:-adr-flow-github-deploy}"

	export WIF_POOL_ID="${WIF_POOL_ID:-github-pool}"
	export WIF_PROVIDER_ID="${WIF_PROVIDER_ID:-github-provider}"
}

gcp_load_env() {
	if [[ -f "${WORKSPACE_ROOT}/.env" ]]; then
		set -a
		# shellcheck disable=SC1091
		source "${WORKSPACE_ROOT}/.env"
		set +a
	fi
	if [[ -f "${GCP_DEPLOY_DIR}/secrets.env" ]]; then
		set -a
		# shellcheck disable=SC1091
		source "${GCP_DEPLOY_DIR}/secrets.env"
		set +a
	fi
	if [[ -f "${GCP_DEPLOY_DIR}/.bootstrap-state.env" ]]; then
		set -a
		# shellcheck disable=SC1091
		source "${GCP_DEPLOY_DIR}/.bootstrap-state.env"
		set +a
	fi
	gcp_apply_defaults
}

gcp_require_gcloud() {
	if ! command -v gcloud >/dev/null 2>&1; then
		echo "error: gcloud CLI not found. Install via devcontainer post-create.d/15-gcloud-cli.sh" >&2
		exit 1
	fi
}

gcp_set_project() {
	gcloud config set project "${GCP_PROJECT_ID}" >/dev/null
	gcloud config set run/region "${GCP_REGION}" >/dev/null 2>&1 || true
}

gcp_project_number() {
	gcloud projects describe "${GCP_PROJECT_ID}" --format='value(projectNumber)'
}

gcp_save_bootstrap_state() {
	local key="$1"
	local value="$2"
	local state_file="${GCP_DEPLOY_DIR}/.bootstrap-state.env"
	touch "${state_file}"
	if grep -q "^${key}=" "${state_file}" 2>/dev/null; then
		# shellcheck disable=SC2034
		local tmp
		tmp="$(mktemp)"
		grep -v "^${key}=" "${state_file}" >"${tmp}" || true
		mv "${tmp}" "${state_file}"
	fi
	printf '%s=%q\n' "${key}" "${value}" >>"${state_file}"
}

gcp_info() {
	printf '==> %s\n' "$*"
}

gcp_warn() {
	printf 'warning: %s\n' "$*" >&2
}
