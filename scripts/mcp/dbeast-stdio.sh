#!/usr/bin/env bash
# Start DBeast MCP with devcontainer DATABASE_URL (Cursor env inheritance can be flaky).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT}/.env"

if [[ -f "${ENV_FILE}" ]]; then
	set -a
	# shellcheck disable=SC1090
	source "${ENV_FILE}"
	set +a
fi

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@postgres:5432/adr_flow}"
export DBEAST_AUDIT_DIR="${DBEAST_AUDIT_DIR:-${ROOT}/logs/mcp_audit}"
mkdir -p "${DBEAST_AUDIT_DIR}"

if ! command -v uv >/dev/null 2>&1; then
	echo "dbeast MCP: uv not found" >&2
	exit 1
fi

tool_dir="$(uv tool dir)/dbeast"
if [[ ! -d "${tool_dir}" ]]; then
	echo "dbeast MCP: not installed — rebuild devcontainer (19-mcp-dbeast.sh)" >&2
	exit 1
fi

server_py="$(find "${tool_dir}/lib" -path '*/site-packages/src/server.py' -print -quit)"
if [[ -z "${server_py}" || ! -f "${server_py}" ]]; then
	echo "dbeast MCP: server.py missing under ${tool_dir}" >&2
	exit 1
fi

exec "${tool_dir}/bin/python" "${server_py}" "$@"
