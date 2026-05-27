# shellcheck shell=bash
# Source from scripts/gcp/*.sh

gcp_require_gcloud_cli() {
	if command -v gcloud >/dev/null 2>&1; then
		return 0
	fi
	echo "gcloud not found. Rebuild the devcontainer, or run once:" >&2
	echo "  bash .devcontainer/post-create.d/15-gcloud-cli.sh" >&2
	return 1
}
