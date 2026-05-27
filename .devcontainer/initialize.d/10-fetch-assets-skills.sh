#!/usr/bin/env bash
# Clones the project-assets repository into .project-assets-cache (host only).
set -euo pipefail

INIT_D_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/assets-common.sh
source "${INIT_D_DIR}/lib/assets-common.sh"
assets_init_paths "${INIT_D_DIR}"

CACHE="${ASSETS_DEVCONTAINER_DIR}/.project-assets-cache"
META="${ASSETS_DEVCONTAINER_DIR}/.project-assets-meta"

assets_load_env

ASSETS_REPO="$(assets_resolve_repo || true)"
if [[ -z "${ASSETS_REPO}" ]]; then
	echo "ASSETS_REPO is not set; skipping project-assets fetch." >&2
	echo "Set ASSETS_REPO in .env or your shell (see .env.example)." >&2
	rm -rf "${CACHE}"
	rm -f "${META}"
	exit 0
fi

SPARSE_PATH="$(assets_resolve_sparse_path ".cursor")"

echo "Fetching project assets from ${ASSETS_REPO} (sparse: ${SPARSE_PATH}) ..."

rm -rf "${CACHE}"
if ! git clone --depth 1 --filter=blob:none --sparse "${ASSETS_REPO}" "${CACHE}"; then
	echo "Failed to clone ${ASSETS_REPO}; skipping project-assets fetch (permissions step still runs)." >&2
	rm -rf "${CACHE}"
	rm -f "${META}"
	exit 0
fi
git -C "${CACHE}" sparse-checkout set "${SPARSE_PATH}"

printf 'SPARSE_PATH=%s\nASSETS_REPO=%s\n' "${SPARSE_PATH}" "${ASSETS_REPO}" >"${META}"
echo "Project assets cached at ${CACHE}"

bash "${INIT_D_DIR}/lib/install-assets-skills.sh"
