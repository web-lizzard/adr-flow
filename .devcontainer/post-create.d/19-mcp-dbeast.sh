#!/usr/bin/env bash
# Install DBeast PostgreSQL MCP server (uv tool from pinned Git tag).
set -euo pipefail

DBEAST_VERSION="${DBEAST_VERSION:-0.2.1}"
DBEAST_GIT_REF="v${DBEAST_VERSION}"
DBEAST_SPEC="dbeast @ git+https://github.com/snss10/DBeast.git@${DBEAST_GIT_REF}"

if ! command -v uv >/dev/null 2>&1; then
	echo "dbeast: uv not found — rebuild the dev container (uv feature installs it)." >&2
	exit 1
fi

dbeast_tool_dir() {
	echo "$(uv tool dir)/dbeast"
}

dbeast_server_py() {
	local tool_dir server_py
	tool_dir="$(dbeast_tool_dir)"
	[[ -d "${tool_dir}" ]] || return 1
	server_py="$(find "${tool_dir}/lib" -path '*/site-packages/src/server.py' -print -quit)"
	[[ -n "${server_py}" && -f "${server_py}" ]] || return 1
	echo "${server_py}"
}

if uv tool list 2>/dev/null | awk '{print $1}' | grep -qx 'dbeast'; then
	receipt="${HOME}/.local/share/uv/tools/dbeast/uv-receipt.toml"
	server_py="$(dbeast_server_py || true)"
	if [[ -n "${server_py}" && -f "${receipt}" ]] && grep -q "rev=${DBEAST_GIT_REF}" "${receipt}"; then
		echo "dbeast already installed: ${DBEAST_GIT_REF} (${server_py})"
		exit 0
	fi
	echo "dbeast present but version mismatch or incomplete; reinstalling ${DBEAST_GIT_REF} ..."
	uv tool uninstall dbeast >/dev/null 2>&1 || true
fi

echo "Installing dbeast ${DBEAST_GIT_REF} via uv tool install ..."
uv tool install "${DBEAST_SPEC}"

server_py="$(dbeast_server_py || true)"
if [[ -z "${server_py}" || ! -f "${server_py}" ]]; then
	echo "dbeast: src/server.py not found after install" >&2
	exit 1
fi

echo "dbeast ${DBEAST_VERSION} installed (server: ${server_py})."
echo "Start via scripts/mcp/dbeast-stdio.sh (upstream 'dbeast' console script entry point is broken)."
