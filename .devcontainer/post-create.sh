#!/usr/bin/env bash
# Runs inside the container after it is created. Add setup steps as scripts in post-create.d/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="${SCRIPT_DIR}/post-create.d"

if [[ ! -d "${HOOKS_DIR}" ]]; then
	echo "No post-create.d directory; nothing to run."
	exit 0
fi

shopt -s nullglob
scripts=("${HOOKS_DIR}"/*.sh)
shopt -u nullglob

if [[ ${#scripts[@]} -eq 0 ]]; then
	echo "No post-create scripts in ${HOOKS_DIR}; nothing to run."
	exit 0
fi

for script in "${scripts[@]}"; do
	echo "==> $(basename "${script}")"
	bash "${script}"
done

echo "Post-create setup finished."

# --- bootstrap-devcontainer 2026-05-27T00:51:43Z ---
# Installs dependencies for scaffolded component(s). Safe to re-run.
cd "${SCRIPT_DIR}/../frontend" && pnpm install
cd "${SCRIPT_DIR}/../backend" && uv sync
