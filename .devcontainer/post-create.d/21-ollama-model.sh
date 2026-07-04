#!/usr/bin/env bash
set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"

if ! command -v curl >/dev/null 2>&1; then
	echo "WARN: curl not available; skip Ollama model pull"
	exit 0
fi

echo "Waiting for Ollama at ${OLLAMA_HOST}..."
ready=false
for _ in $(seq 1 30); do
	if curl -fsS "${OLLAMA_HOST}/api/version" >/dev/null 2>&1; then
		ready=true
		break
	fi
	sleep 2
done

if [[ "${ready}" != "true" ]]; then
	echo "WARN: Ollama not reachable; skip model pull (rebuild devcontainer after compose change)"
	exit 0
fi

echo "Pulling Ollama model ${OLLAMA_MODEL} (one-time download; persisted in ollama-data volume)..."
curl -fsS "${OLLAMA_HOST}/api/pull" \
	-H "Content-Type: application/json" \
	-d "{\"name\":\"${OLLAMA_MODEL}\"}" \
	--no-buffer >/dev/null

echo "Ollama model ${OLLAMA_MODEL} ready"
