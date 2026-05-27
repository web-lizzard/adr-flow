#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_require-gcloud.sh
source "${SCRIPT_DIR}/_require-gcloud.sh"

gcp_require_gcloud_cli
gcloud auth login --no-launch-browser
