#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_require-gcloud.sh
source "${SCRIPT_DIR}/_require-gcloud.sh"

gcp_require_gcloud_cli

echo "=== gcloud version ==="
gcloud --version | head -n1
echo ""
echo "=== accounts ==="
gcloud auth list 2>/dev/null || true
echo ""
project="$(gcloud config get-value project 2>/dev/null || true)"
if [[ -n "${project}" && "${project}" != "(unset)" ]]; then
	echo "Active project: ${project}"
else
	echo "Active project: (unset) — after bootstrap: gcloud config set project adr-flow"
fi
region="$(gcloud config get-value run/region 2>/dev/null || true)"
if [[ -n "${region}" && "${region}" != "(unset)" ]]; then
	echo "Cloud Run region: ${region}"
else
	echo "Cloud Run region: (unset) — suggested: gcloud config set run/region europe-west1"
fi
echo ""
echo "To log in: just gcp-auth-login"
