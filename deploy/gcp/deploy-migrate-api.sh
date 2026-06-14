#!/usr/bin/env bash
# Deploy and execute the adr-flow-api-migrate Cloud Run Job.
# Runs `alembic upgrade head` against the production Postgres VM via VPC egress.
# Safe to run on every deploy — upgrading an already-current database is a no-op.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud
gcp_set_project

MIGRATE_JOB_NAME="${MIGRATE_JOB_NAME:-adr-flow-api-migrate}"
API_RUN_SA_EMAIL="${API_RUN_SA_EMAIL:-${API_RUN_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com}"

if ! gcloud iam service-accounts describe "${API_RUN_SA_EMAIL}" \
	--project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
	echo "error: API runtime SA ${API_RUN_SA_EMAIL} not found. Run deploy/gcp/04-secrets.sh first." >&2
	exit 1
fi

FLAGS_FILE="${SCRIPT_DIR}/run-migrate-api.flags"
if [[ ! -f "${FLAGS_FILE}" ]]; then
	echo "error: missing ${FLAGS_FILE}" >&2
	exit 1
fi

# shellcheck disable=SC2046
DEPLOY_FLAGS=($(grep -v '^[[:space:]]*#' "${FLAGS_FILE}" | grep -v '^[[:space:]]*$'))

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

gcp_info "Deploying migration job ${MIGRATE_JOB_NAME} from ${WORKSPACE_ROOT}/backend (uv buildpack)"
# Jobs deploy does not support --set-build-env-vars (services only). uv activates
# automatically when pyproject.toml and uv.lock are present in the source root.
# Runtime: use the buildpack launcher to run Alembic from the installed venv.
# Plain `uv` / `alembic` are not on PATH when --command overrides the image entrypoint.
gcloud run jobs deploy "${MIGRATE_JOB_NAME}" \
	--source "${WORKSPACE_ROOT}/backend" \
	--project="${GCP_PROJECT_ID}" \
	--region="${GCP_REGION}" \
	--service-account="${API_RUN_SA_EMAIL}" \
	--command=launcher \
	--args=python,-m,alembic,upgrade,head \
	--tasks=1 \
	--parallelism=1 \
	--max-retries=0 \
	"${DEPLOY_FLAGS[@]}"

gcp_info "Executing migration job ${MIGRATE_JOB_NAME}"
if ! gcloud run jobs execute "${MIGRATE_JOB_NAME}" \
	--project="${GCP_PROJECT_ID}" \
	--region="${GCP_REGION}" \
	--wait; then
	echo "error: migration job failed. Inspect logs:" >&2
	echo "  gcloud run jobs executions list --job=${MIGRATE_JOB_NAME} --region=${GCP_REGION} --project=${GCP_PROJECT_ID}" >&2
	echo "  gcloud logging read 'resource.labels.job_name=\"${MIGRATE_JOB_NAME}\"' --project=${GCP_PROJECT_ID} --limit=50 --format=json" >&2
	exit 1
fi

gcp_info "Migration job ${MIGRATE_JOB_NAME} completed successfully"
