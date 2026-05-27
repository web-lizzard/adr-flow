#!/usr/bin/env bash
# Install frontend/backend dependencies (requires node + uv devcontainer features).
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NVM_DIR="${NVM_DIR:-/usr/local/share/nvm}"

if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
	# shellcheck source=/dev/null
	. "${NVM_DIR}/nvm.sh"
	nvm use 22 >/dev/null 2>&1 || nvm use default >/dev/null
fi

if ! command -v pnpm >/dev/null 2>&1; then
	echo "pnpm not found — rebuild the dev container (node feature installs it)." >&2
	exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
	echo "uv not found — rebuild the dev container (uv feature installs it)." >&2
	exit 1
fi

echo "Installing frontend dependencies ..."
cd "${WORKSPACE_ROOT}/frontend"
pnpm install

echo "Installing backend dependencies ..."
cd "${WORKSPACE_ROOT}/backend"
uv sync

echo "Project dependencies installed."
