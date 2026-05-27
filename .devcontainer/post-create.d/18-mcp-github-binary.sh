#!/usr/bin/env bash
# Install github-mcp-server binary for devcontainer MCP (no Docker).
set -euo pipefail

GITHUB_MCP_VERSION="${GITHUB_MCP_VERSION:-1.0.5}"
INSTALL_PATH="/usr/local/bin/github-mcp-server"
RELEASE_BASE="https://github.com/github/github-mcp-server/releases/download/v${GITHUB_MCP_VERSION}"

case "$(uname -m)" in
x86_64 | amd64)
	ARCHIVE="github-mcp-server_Linux_x86_64.tar.gz"
	;;
aarch64 | arm64)
	ARCHIVE="github-mcp-server_Linux_arm64.tar.gz"
	;;
*)
	echo "github-mcp-server: unsupported Linux architecture: $(uname -m)" >&2
	exit 1
	;;
esac

if [[ -x "${INSTALL_PATH}" ]]; then
	installed_version="$("${INSTALL_PATH}" --version 2>/dev/null | awk '/^Version:/ { print $2; exit }')"
	if [[ "${installed_version}" == "${GITHUB_MCP_VERSION}" ]]; then
		echo "github-mcp-server already installed: ${installed_version} (${INSTALL_PATH})"
		exit 0
	fi
	echo "github-mcp-server ${installed_version:-unknown} at ${INSTALL_PATH}; upgrading to ${GITHUB_MCP_VERSION} ..."
fi

if ! command -v curl >/dev/null 2>&1; then
	echo "github-mcp-server: curl is required but not installed." >&2
	exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
	echo "github-mcp-server: tar is required but not installed." >&2
	exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

download_url="${RELEASE_BASE}/${ARCHIVE}"
echo "Installing github-mcp-server ${GITHUB_MCP_VERSION} (${ARCHIVE}) ..."
curl -fsSL "${download_url}" -o "${tmpdir}/archive.tar.gz"
tar -xzf "${tmpdir}/archive.tar.gz" -C "${tmpdir}"

if [[ ! -f "${tmpdir}/github-mcp-server" ]]; then
	echo "github-mcp-server: expected binary missing in ${ARCHIVE}" >&2
	exit 1
fi

sudo install -m 0755 "${tmpdir}/github-mcp-server" "${INSTALL_PATH}"

installed_version="$("${INSTALL_PATH}" --version 2>/dev/null | awk '/^Version:/ { print $2; exit }')"
if [[ "${installed_version}" != "${GITHUB_MCP_VERSION}" ]]; then
	echo "github-mcp-server: installed version ${installed_version:-unknown} != ${GITHUB_MCP_VERSION}" >&2
	exit 1
fi

echo "github-mcp-server ${installed_version} installed at ${INSTALL_PATH}."
