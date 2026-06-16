#!/usr/bin/env bash
# Run stack-aware lint/format after agent file edits.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

if should_skip_path; then
	exit 0
fi

stack="$(detect_stack)"
if [[ "$stack" == skip ]]; then
	exit 0
fi

log() {
	echo "[cursor-hook:lint] $*" >&2
}

run_lint() {
	local status=0

	case "$stack" in
	frontend)
		local frontend_rel
		frontend_rel="$(frontend_rel_path)"

		log "frontend → eslint + prettier (${REL_PATH})"
		if ! run_in_frontend ./node_modules/.bin/eslint --fix --no-warn-ignored "$frontend_rel"; then
			status=1
		fi
		if ! run_in_frontend ./node_modules/.bin/prettier --write "$frontend_rel"; then
			status=1
		fi
		;;
	backend)
		local backend_rel
		backend_rel="$(backend_rel_path)"

		log "backend → ruff check + format (${REL_PATH})"
		if ! run_in_backend ruff check --fix "$backend_rel"; then
			status=1
		fi
		if ! run_in_backend ruff format "$backend_rel"; then
			status=1
		fi
		;;
	esac

	return "$status"
}

if ! run_lint; then
	log "lint finished with errors (agent flow continues)"
fi

exit 0
