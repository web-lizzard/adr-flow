#!/usr/bin/env bash
# Copies skills from .project-assets-cache into workspace .cursor/skills.
# Invoked from 10-fetch-assets-skills.sh (not run directly by initialize.sh).
set -euo pipefail

INIT_D_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=assets-common.sh
source "${INIT_D_DIR}/lib/assets-common.sh"
assets_init_paths "${INIT_D_DIR}"

META_FILE="${ASSETS_DEVCONTAINER_DIR}/.project-assets-meta"
CACHE="${ASSETS_DEVCONTAINER_DIR}/.project-assets-cache"
DEST="${ASSETS_WORKSPACE_ROOT}/.cursor/skills"

if [[ ! -f "${META_FILE}" ]]; then
	echo "No project-assets metadata (.project-assets-meta); skipping Cursor skills install."
	exit 0
fi

# shellcheck disable=SC1090
source "${META_FILE}"
SPARSE_PATH="${SPARSE_PATH:-.cursor}"

if [[ "${SPARSE_PATH}" == ".cursor" || "${SPARSE_PATH}" == ".cursor/" ]]; then
	SRC="${CACHE}/.cursor/skills"
else
	SRC="${CACHE}/${SPARSE_PATH}"
	if [[ "${SPARSE_PATH}" == "." ]]; then
		SRC="${CACHE}"
	fi
fi

if [[ ! -d "${SRC}" ]]; then
	echo "Skills source not found at ${SRC}; skipping install." >&2
	exit 1
fi

mkdir -p "${DEST}"
find "${DEST}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp -a "${SRC}/." "${DEST}/"

if [[ ! -d "${DEST}" ]] || [[ -z "$(find "${DEST}" -mindepth 1 -print -quit 2>/dev/null)" ]]; then
	echo "Skills install failed: ${DEST} is empty after copy." >&2
	exit 1
fi

echo "Installed Cursor skills into ${DEST}"
