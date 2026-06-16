#!/usr/bin/env bash
# Shared helpers for Cursor afterFileEdit hooks.
set -euo pipefail

HOOK_INPUT="$(cat)"
FILE_PATH="$(jq -r '.file_path // empty' <<<"$HOOK_INPUT")"
WORKSPACE_ROOT="$(jq -r '.workspace_roots[0] // empty' <<<"$HOOK_INPUT")"

if [[ -z "$WORKSPACE_ROOT" ]]; then
	WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
fi

if [[ -z "$FILE_PATH" ]]; then
	exit 0
fi

if [[ "$FILE_PATH" != /* ]]; then
	FILE_PATH="${WORKSPACE_ROOT}/${FILE_PATH}"
fi

REL_PATH="${FILE_PATH#"${WORKSPACE_ROOT}/"}"
REL_PATH="${REL_PATH#/}"

should_skip_path() {
	case "$REL_PATH" in
	node_modules/* | */node_modules/* | .venv/* | */.venv/* | dist/* | */dist/* | .nuxt/* | */.nuxt/* | .output/* | */.output/* | context/* | .cursor/skills/* | .cursor/rules/*)
		return 0
		;;
	esac
	return 1
}

detect_stack() {
	case "$REL_PATH" in
	frontend/*)
		case "$REL_PATH" in
		*.ts | *.tsx | *.vue | *.js | *.mjs | *.cjs) echo frontend ;;
		*) echo skip ;;
		esac
		;;
	backend/*)
		case "$REL_PATH" in
		*.py) echo backend ;;
		*) echo skip ;;
		esac
		;;
	*) echo skip ;;
	esac
}

frontend_rel_path() {
	echo "${REL_PATH#frontend/}"
}

backend_rel_path() {
	echo "${REL_PATH#backend/}"
}

run_in_frontend() {
	bash "${WORKSPACE_ROOT}/.pre-commit/run-in-frontend.sh" "$@"
}

run_in_backend() {
	(
		cd "${WORKSPACE_ROOT}/backend"
		uv run "$@"
	)
}

resolve_pytest_targets() {
	local targets=()

	case "$REL_PATH" in
	backend/tests/* | backend/**/test_*.py)
		targets+=("$(backend_rel_path)")
		;;
	backend/*.py | backend/**/*.py)
		local src_rel backend_rel dir base candidate

		backend_rel="$(backend_rel_path)"
		src_rel="$backend_rel"
		dir="$(dirname "$src_rel")"
		base="$(basename "$src_rel" .py)"

		if [[ "$base" == "__init__" ]]; then
			if [[ -d "${WORKSPACE_ROOT}/backend/tests/${dir}" ]]; then
				while IFS= read -r test_file; do
					targets+=("${test_file#"${WORKSPACE_ROOT}/backend/"}")
				done < <(find "${WORKSPACE_ROOT}/backend/tests/${dir}" -maxdepth 1 -name 'test_*.py' -type f 2>/dev/null | sort)
			fi
		else
			if [[ "$dir" == "." ]]; then
				candidate="tests/test_${base}.py"
			else
				candidate="tests/${dir}/test_${base}.py"
			fi

			if [[ -f "${WORKSPACE_ROOT}/backend/${candidate}" ]]; then
				targets+=("$candidate")
			fi
		fi
		;;
	esac

	if ((${#targets[@]} == 0)); then
		return 0
	fi

	printf '%s\n' "${targets[@]}" | sort -u
}
