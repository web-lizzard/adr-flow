#!/usr/bin/env bash
# Verifies permissions.json is present (bind-mounted from .devcontainer/.permissions-cache).
set -euo pipefail

DEST="/home/vscode/.cursor/permissions.json"

if [[ ! -f "${DEST}" ]]; then
	echo "No ${DEST}; rebuild container after adding .cursor/permissions.json." >&2
	exit 0
fi

if [[ "$(tr -d '[:space:]' <"${DEST}")" == "{}" ]]; then
	echo "permissions.json is empty; Cursor will use the in-app allowlist." >&2
	exit 0
fi

echo "Cursor permissions available at ${DEST}"
