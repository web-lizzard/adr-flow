#!/usr/bin/env bash
# Read-only MCP prerequisites check (devcontainer). See .devcontainer/MCP.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT}/.env"

fail=0

echo "=== MCP verify (devcontainer) ==="
echo ""

if [[ ! -f "${ENV_FILE}" ]]; then
	echo "FAIL: ${ENV_FILE} missing"
	echo "  cp .env.example .env"
	echo "  Then set GITHUB_PERSONAL_ACCESS_TOKEN (see .devcontainer/MCP.md)."
	fail=1
else
	# shellcheck disable=SC1090
	source "${ENV_FILE}"
	if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
		echo "FAIL: GITHUB_PERSONAL_ACCESS_TOKEN is empty in ${ENV_FILE}"
		fail=1
	else
		echo "OK: .env present and GITHUB_PERSONAL_ACCESS_TOKEN is set"
	fi
fi

echo ""
echo "=== commands ==="
for cmd in gcloud github-mcp-server npx; do
	if command -v "${cmd}" >/dev/null 2>&1; then
		echo "OK: ${cmd} -> $(command -v "${cmd}")"
	else
		echo "FAIL: ${cmd} not found"
		fail=1
	fi
done

if command -v github-mcp-server >/dev/null 2>&1; then
	echo "    version: $(github-mcp-server --version 2>/dev/null || true)"
fi

echo ""
echo "=== gcloud (non-destructive) ==="
if command -v gcloud >/dev/null 2>&1; then
	gcloud auth list 2>/dev/null || true
	echo ""
	project="$(gcloud config get-value project 2>/dev/null || true)"
	if [[ -n "${project}" && "${project}" != "(unset)" ]]; then
		echo "Active project: ${project}"
	else
		echo "Active project: (unset) — run: gcloud config set project adr-flow"
	fi
	region="$(gcloud config get-value run/region 2>/dev/null || true)"
	if [[ -n "${region}" && "${region}" != "(unset)" ]]; then
		echo "Cloud Run region: ${region}"
	else
		echo "Cloud Run region: (unset) — run: gcloud config set run/region europe-west1"
	fi
else
	echo "(skipped — gcloud not installed)"
fi

echo ""
echo "=== Cursor UI (manual) ==="
echo "After rebuild, confirm in Cursor: Settings → MCP (or MCP Logs) that"
echo "  gcloud, gcp-observability, and github are connected."
echo "Process paths must be under /home/vscode or /workspace, not host paths."
echo "Full checklist: .devcontainer/MCP.md"
echo ""

if [[ "${fail}" -ne 0 ]]; then
	exit 1
fi
echo "Shell checks passed."
