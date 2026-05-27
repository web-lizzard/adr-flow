# Shared paths and helpers for initialize.d host scripts.
# shellcheck shell=bash

assets_init_paths() {
	local initialize_d_dir="$1"
	ASSETS_DEVCONTAINER_DIR="$(cd "${initialize_d_dir}/.." && pwd)"
	ASSETS_WORKSPACE_ROOT="$(cd "${ASSETS_DEVCONTAINER_DIR}/.." && pwd)"
}

assets_load_env() {
	if [[ -f "${ASSETS_WORKSPACE_ROOT}/.env" ]]; then
		set -a
		# shellcheck disable=SC1091
		source "${ASSETS_WORKSPACE_ROOT}/.env"
		set +a
	fi
}

assets_resolve_repo() {
	if [[ -n "${ASSETS_REPO:-}" ]]; then
		printf '%s' "${ASSETS_REPO}"
	fi
}

assets_resolve_sparse_path() {
	local default="$1"
	if [[ -n "${ASSETS_SPARSE_PATH:-}" ]]; then
		printf '%s' "${ASSETS_SPARSE_PATH}"
	else
		printf '%s' "${default}"
	fi
}
