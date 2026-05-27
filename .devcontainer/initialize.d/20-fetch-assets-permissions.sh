#!/usr/bin/env bash
# Copies permissions from project-assets cache into .permissions-cache for container bind-mount.
# Source of truth: ASSETS_REPO (.cursor/permissions.json), not workspace overrides.
set -euo pipefail

INIT_D_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/assets-common.sh
source "${INIT_D_DIR}/lib/assets-common.sh"
assets_init_paths "${INIT_D_DIR}"

PROJECT_ASSETS_CACHE="${ASSETS_DEVCONTAINER_DIR}/.project-assets-cache"
PERMISSIONS_CACHE_DIR="${ASSETS_DEVCONTAINER_DIR}/.permissions-cache"
OUT="${PERMISSIONS_CACHE_DIR}/permissions.json"
META="${ASSETS_DEVCONTAINER_DIR}/.permissions-meta"
CACHED_FILE="${PROJECT_ASSETS_CACHE}/.cursor/permissions.json"

assets_load_env

mkdir -p "${PERMISSIONS_CACHE_DIR}"
rm -f "${META}"

resolve_from_path() {
	local src="$1"
	cp -f "${src}" "${OUT}"
	printf 'SOURCE=%s\n' "${src}" >"${META}"
}

validate_json() {
	if command -v python3 >/dev/null 2>&1; then
		python3 -m json.tool "${OUT}" >/dev/null
	elif command -v jq >/dev/null 2>&1; then
		jq empty "${OUT}" >/dev/null
	else
		echo "Warning: python3/jq not found; skipping JSON validation for ${OUT}" >&2
	fi
}

write_empty() {
	printf '{}\n' >"${OUT}"
	rm -f "${META}"
}

if [[ -f "${CACHED_FILE}" ]]; then
	echo "Using project-assets permissions: ${CACHED_FILE}"
	resolve_from_path "${CACHED_FILE}"
	validate_json
	echo "Permissions cached at ${OUT} (mounted into container as ~/.cursor/permissions.json)"
	exit 0
fi

ASSETS_REPO="$(assets_resolve_repo || true)"
if [[ -n "${ASSETS_REPO}" ]]; then
	echo "ASSETS_REPO is set but ${CACHED_FILE} is missing." >&2
	echo "Fix step 10-fetch (SSH access, repo layout) so .cursor/permissions.json is cloned." >&2
fi

write_empty
echo "Using empty permissions cache; Cursor will use the in-app allowlist." >&2
exit 0
