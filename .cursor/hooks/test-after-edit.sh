#!/usr/bin/env bash
# Run stack-aware related tests after agent file edits.
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
	echo "[cursor-hook:test] $*" >&2
}

run_tests() {
	local status=0

	case "$stack" in
	frontend)
		local frontend_rel
		frontend_rel="$(frontend_rel_path)"

		log "frontend → vitest related (${REL_PATH})"
		if ! run_in_frontend ./node_modules/.bin/vitest related "$frontend_rel" --run --passWithNoTests; then
			status=1
		fi
		;;
	backend)
		local -a targets=()
		while IFS= read -r target; do
			[[ -n "$target" ]] && targets+=("$target")
		done < <(resolve_pytest_targets)

		if ((${#targets[@]} == 0)); then
			log "backend → no related pytest targets for ${REL_PATH}"
			return 0
		fi

		log "backend → pytest ${targets[*]}"
		if ! run_in_backend pytest "${targets[@]}"; then
			status=1
		fi
		;;
	esac

	return "$status"
}

if ! run_tests; then
	log "tests finished with failures (agent flow continues)"
fi

exit 0
