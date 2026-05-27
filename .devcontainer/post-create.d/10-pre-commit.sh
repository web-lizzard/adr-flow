#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${WORKSPACE_ROOT}"

if ! command -v pre-commit >/dev/null 2>&1; then
	echo "Installing pre-commit ..."
	sudo apt-get update -qq
	sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq pre-commit
fi

pre-commit install

echo "pre-commit hooks installed."

