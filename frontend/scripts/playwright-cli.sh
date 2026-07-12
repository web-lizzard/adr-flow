#!/usr/bin/env bash
# Wrapper: ensure virtual display is up and DISPLAY is set for headed mode.
set -euo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_ROOT="$(cd "${FRONTEND_DIR}/.." && pwd)"
CLI="${FRONTEND_DIR}/node_modules/.bin/playwright-cli"

if [[ -x "${WORKSPACE_ROOT}/.devcontainer/bin/start-display.sh" ]]; then
	bash "${WORKSPACE_ROOT}/.devcontainer/bin/start-display.sh" >/dev/null 2>&1 || true
fi

export DISPLAY="${DISPLAY:-:99}"
exec "${CLI}" "$@"
