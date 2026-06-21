#!/bin/sh
set -e

MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

ollama serve &
SERVER_PID=$!

echo "Waiting for Ollama to be ready..."
for _ in $(seq 1 120); do
  if ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! ollama list >/dev/null 2>&1; then
  echo "Ollama failed to start" >&2
  exit 1
fi

echo "Pulling generation model: ${MODEL}"
ollama pull "${MODEL}"

if [ -n "${EMBED_MODEL}" ]; then
  echo "Pulling embedding model: ${EMBED_MODEL}"
  ollama pull "${EMBED_MODEL}"
fi

echo "Ollama ready with models: ${MODEL}, ${EMBED_MODEL}"
wait "${SERVER_PID}"
