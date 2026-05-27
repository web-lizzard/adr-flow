#!/usr/bin/env bash
# Deploy adr-flow-web: Cloud Build (frontend/) → Artifact Registry → Cloud Run (Nuxt SSR).
# No local Docker required — only gcloud in the devcontainer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gcp_load_env
gcp_require_gcloud
gcp_set_project

WEB_SERVICE="${WEB_SERVICE:-adr-flow-web}"
API_SERVICE="${API_SERVICE:-adr-flow-api}"
TAG="${TAG:-latest}"

if [[ -z "${AR_IMAGE_PREFIX:-}" ]]; then
	echo "error: AR_IMAGE_PREFIX not set. Run deploy/gcp/06-artifact-registry.sh first." >&2
	exit 1
fi

IMAGE="${AR_IMAGE_PREFIX}/${WEB_SERVICE}:${TAG}"

FLAGS_FILE="${SCRIPT_DIR}/run-web.flags"
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

API_URL="$(
	gcloud run services describe "${API_SERVICE}" \
		--project="${GCP_PROJECT_ID}" \
		--region="${GCP_REGION}" \
		--format='value(status.url)' 2>/dev/null || true
)"
if [[ -z "${API_URL}" ]]; then
	echo "error: ${API_SERVICE} is not deployed. Deploy the API first: just gcp-deploy-api" >&2
	exit 1
fi
API_URL="${API_URL%/}"

gcp_info "Cloud Build: ${IMAGE} from ${WORKSPACE_ROOT}/frontend (no local Docker)"
gcloud builds submit "${WORKSPACE_ROOT}/frontend" \
	--project="${GCP_PROJECT_ID}" \
	--region="${GCP_REGION}" \
	--tag="${IMAGE}"

gcp_info "Deploying ${WEB_SERVICE} (NUXT_API_UPSTREAM=${API_URL})"
gcloud run deploy "${WEB_SERVICE}" \
	--image "${IMAGE}" \
	--project="${GCP_PROJECT_ID}" \
	--set-env-vars="NUXT_API_UPSTREAM=${API_URL}" \
	"${DEPLOY_FLAGS[@]}"

WEB_URL="$(
	gcloud run services describe "${WEB_SERVICE}" \
		--project="${GCP_PROJECT_ID}" \
		--region="${GCP_REGION}" \
		--format='value(status.url)'
)"
WEB_URL="${WEB_URL%/}"

cat <<EOF

Web service deployed.

  URL: ${WEB_URL}
  Proxy smoke: curl ${WEB_URL}/api/health
  UI: open ${WEB_URL}/ in a browser (home page shows API health via /api/health)

EOF
