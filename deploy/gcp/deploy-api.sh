#!/usr/bin/env bash
# Deploy adr-flow-api from backend/ via Cloud Run source + uv (pyproject.toml + uv.lock).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud
gcp_set_project

API_SERVICE="${API_SERVICE:-adr-flow-api}"
API_RUN_SA_EMAIL="${API_RUN_SA_EMAIL:-${API_RUN_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"

if ! gcloud iam service-accounts describe "${API_RUN_SA_EMAIL}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	echo "error: API runtime SA ${API_RUN_SA_EMAIL} not found. Run deploy/gcp/04-secrets.sh first." >&2
	exit 1
fi

FLAGS_FILE="${SCRIPT_DIR}/run-api.flags"
if [[ ! -f "${FLAGS_FILE}" ]]; then
	echo "error: missing ${FLAGS_FILE}" >&2
	exit 1
fi

# shellcheck disable=SC2046
DEPLOY_FLAGS=($(grep -v '^[[:space:]]*#' "${FLAGS_FILE}" | grep -v '^[[:space:]]*$'))

# Substitute region/subnet from env when defaults in run-api.flags differ.
deploy_flag() {
	local name="$1"
	local value="$2"
	local i
	for ((i = 0; i < ${#DEPLOY_FLAGS[@]}; i++)); do
		if [[ "${DEPLOY_FLAGS[i]}" == "${name}"* ]]; then
			DEPLOY_FLAGS[i]="${name}=${value}"
			return
		fi
	done
	DEPLOY_FLAGS+=("${name}=${value}")
}

deploy_flag "--region" "${GCP_REGION}"
deploy_flag "--subnet" "${CLOUD_RUN_SUBNET}"

gcp_info "Deploying ${API_SERVICE} from ${WORKSPACE_ROOT}/backend (uv buildpack)"
gcloud run deploy "${API_SERVICE}" \
	--source "${WORKSPACE_ROOT}/backend" \
	--project="${GCP_PROJECT_ID}" \
	--set-build-env-vars=GOOGLE_PYTHON_PACKAGE_MANAGER=uv \
	--service-account="${API_RUN_SA_EMAIL}" \
	"${DEPLOY_FLAGS[@]}"

gcp_info "API URL: $(gcloud run services describe "${API_SERVICE}" \
	--project="${GCP_PROJECT_ID}" \
	--region="${GCP_REGION}" \
	--format='value(status.url)')"
