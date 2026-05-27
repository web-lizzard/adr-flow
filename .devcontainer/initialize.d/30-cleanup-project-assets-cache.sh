#!/usr/bin/env bash
# Removes the git clone cache after skills and permissions have been resolved.
set -euo pipefail

INIT_D_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/assets-common.sh
source "${INIT_D_DIR}/lib/assets-common.sh"
assets_init_paths "${INIT_D_DIR}"

CACHE="${ASSETS_DEVCONTAINER_DIR}/.project-assets-cache"
META="${ASSETS_DEVCONTAINER_DIR}/.project-assets-meta"

if [[ -d "${CACHE}" || -f "${META}" ]]; then
	rm -rf "${CACHE}"
	rm -f "${META}"
	echo "Removed project-assets git cache."
fi
