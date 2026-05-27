#!/usr/bin/env bash
# Runs on the host during devcontainer initialize. Add steps as scripts in initialize.d/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_DIR="${SCRIPT_DIR}/initialize.d"

if [[ ! -d "${HOOKS_DIR}" ]]; then
	echo "No initialize.d directory; nothing to run."
	exit 0
fi

shopt -s nullglob
scripts=("${HOOKS_DIR}"/*.sh)
shopt -u nullglob

if [[ ${#scripts[@]} -eq 0 ]]; then
	echo "No initialize scripts in ${HOOKS_DIR}; nothing to run."
	exit 0
fi

for script in "${scripts[@]}"; do
	echo "==> $(basename "${script}")"
	bash "${script}"
done

echo "Initialize setup finished."
