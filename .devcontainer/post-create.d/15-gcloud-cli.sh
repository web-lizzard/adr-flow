#!/usr/bin/env bash
set -euo pipefail

if command -v gcloud >/dev/null 2>&1; then
	echo "gcloud already installed: $(gcloud --version 2>/dev/null | head -n1)"
	exit 0
fi

echo "Installing Google Cloud CLI ..."

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
	apt-transport-https \
	ca-certificates \
	curl \
	gnupg

curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list >/dev/null

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq google-cloud-cli

gcloud --version | head -n1
echo "gcloud CLI installed. Run: gcloud auth login --no-launch-browser"
