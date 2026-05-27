#!/usr/bin/env bash
# Run a command in frontend/ with Node 22 from nvm when available.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NVM_DIR="${NVM_DIR:-/usr/local/share/nvm}"

if [[ -s "${NVM_DIR}/nvm.sh" ]]; then
	# shellcheck source=/dev/null
	. "${NVM_DIR}/nvm.sh"
	nvm use 22 >/dev/null
fi

cd "${ROOT}/frontend"
exec "$@"
