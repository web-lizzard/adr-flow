#!/usr/bin/env bash
# Ensure the in-container display stack is running and print how to open noVNC.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DISPLAY_NUM="${DISPLAY_NUM:-99}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
URL="http://localhost:${NOVNC_PORT}/vnc.html"

bash "${SCRIPT_DIR}/start-display.sh" >/dev/null

if curl -sf "${URL}" >/dev/null; then
	echo "noVNC is running."
else
	echo "noVNC is not responding on port ${NOVNC_PORT}." >&2
	echo "Rebuild the dev container if you have not since adding noVNC." >&2
	exit 1
fi

cat <<EOF

Open this URL in your HOST browser (Safari/Chrome on your Mac) — not in the terminal:

  ${URL}

In Cursor: Ports tab → ${NOVNC_PORT} → Open in Browser.

Then run headed Playwright in the terminal:

  cd frontend
  pnpm run playwright open http://localhost:3000 --headed

You should see Chromium inside the noVNC desktop. Close with:

  pnpm run playwright close

EOF
