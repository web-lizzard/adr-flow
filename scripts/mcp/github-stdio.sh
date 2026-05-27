#!/usr/bin/env bash
# Start github-mcp-server with root .env loaded (Cursor envFile can fail in devcontainers).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT}/.env"

if [[ -f "${ENV_FILE}" ]]; then
	set -a
	# shellcheck disable=SC1090
	source "${ENV_FILE}"
	set +a
fi

exec /usr/local/bin/github-mcp-server stdio "$@"
