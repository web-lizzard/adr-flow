#!/usr/bin/env bash
set -euo pipefail

GCLOUD_CONFIG_DIR="/home/vscode/.config/gcloud"

if [[ ! -d "${GCLOUD_CONFIG_DIR}" ]]; then
	exit 0
fi

owner="$(stat -c '%U:%G' "${GCLOUD_CONFIG_DIR}")"
if [[ "${owner}" == "vscode:vscode" ]]; then
	exit 0
fi

echo "Fixing ownership of ${GCLOUD_CONFIG_DIR} (was ${owner}) ..."
sudo chown -R vscode:vscode "${GCLOUD_CONFIG_DIR}"
