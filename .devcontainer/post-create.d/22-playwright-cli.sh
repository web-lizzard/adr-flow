#!/usr/bin/env bash
# Initialize playwright-cli in frontend/ and install browser + OS deps.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FRONTEND="${WORKSPACE_ROOT}/frontend"
NVM_DIR="${NVM_DIR:-/usr/local/share/nvm}"

if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
	# shellcheck source=/dev/null
	. "${NVM_DIR}/nvm.sh"
	nvm use 22 >/dev/null 2>&1 || nvm use default >/dev/null
fi

if [[ ! -f "${FRONTEND}/node_modules/.bin/playwright-cli" ]]; then
	echo "playwright-cli not found — run 17-project-deps.sh first." >&2
	exit 1
fi

echo "Initializing playwright-cli workspace ..."
cd "${FRONTEND}"
./node_modules/.bin/playwright-cli install --skills=agents
./node_modules/.bin/playwright-cli install-browser

PLAYWRIGHT_CORE="$(find node_modules -path '*/playwright-core/cli.js' -print -quit)"
if [[ -n "${PLAYWRIGHT_CORE}" ]]; then
	echo "Installing Playwright browser system dependencies ..."
	sudo env "PATH=${PATH}" node "${PLAYWRIGHT_CORE}" install-deps chromium
fi

echo "playwright-cli initialized."
