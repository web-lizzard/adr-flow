#!/usr/bin/env bash
set -euo pipefail

if command -v just >/dev/null 2>&1; then
	echo "just already installed: $(just --version)"
	exit 0
fi

echo "Installing just ..."
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq just

just --version
echo "just installed."
