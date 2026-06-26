#!/usr/bin/env bash
#
# scrape-native.sh — Run the scraper with Ollama on bare metal (Metal GPU).
#
# Falls back to the Docker Ollama container when the native binary is not
# installed.  ChromaDB always runs in Docker.
#
# Usage:
#   ./scripts/scrape-native.sh <URL> [extra scraper flags...]
#
# Examples:
#   ./scripts/scrape-native.sh https://hermes-agent.nousresearch.com/docs -y
#   ./scripts/scrape-native.sh https://example.com/docs -y --no-llm-clean --max-files 50
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

MODEL="${OLLAMA_MODEL:-qwen2.5:1.5b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
OLLAMA_PORT="${OLLAMA_PORT:-11434}"
OLLAMA_URL="http://localhost:${OLLAMA_PORT}"

NATIVE_OLLAMA=""
STARTED_OLLAMA=false
STOPPED_DOCKER_OLLAMA=false

cleanup() {
  if [ "$STARTED_OLLAMA" = true ]; then
    echo ""
    echo "Stopping Ollama that we started (pid file)..."
    pkill -f "ollama serve" 2>/dev/null || true
  fi
  if [ "$STOPPED_DOCKER_OLLAMA" = true ]; then
    echo "Restarting Docker Ollama container..."
    docker start scraper-ollama >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# ── 1. Detect native Ollama ─────────────────────────────────────────────────
if command -v ollama >/dev/null 2>&1; then
  NATIVE_OLLAMA="$(command -v ollama)"
  echo "Native Ollama found: ${NATIVE_OLLAMA}"
else
  echo "Native Ollama not found. Install with: brew install ollama"
  echo "Falling back to Docker Ollama (CPU-only on macOS)."
  cd "$REPO_ROOT"
  docker compose up -d ollama chromadb
  echo "Waiting for Docker Ollama to become healthy..."
  for i in $(seq 1 60); do
    if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
      echo "Docker Ollama ready."
      break
    fi
    sleep 2
  done
  exec "${REPO_ROOT}/.venv/bin/python" -m web_scraper scrape "$@" \
    --model "$MODEL" --embed-model "$EMBED_MODEL"
fi

# ── 2. Free port 11434 if Docker Ollama is occupying it ─────────────────────
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q scraper-ollama; then
  echo "Stopping Docker Ollama container to free port ${OLLAMA_PORT}..."
  docker stop scraper-ollama >/dev/null 2>&1 || true
  STOPPED_DOCKER_OLLAMA=true
  sleep 1
fi

# ── 3. Start native Ollama if not already running ───────────────────────────
if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  echo "Native Ollama already running at ${OLLAMA_URL}."
else
  echo "Starting native Ollama (Metal GPU)..."
  ollama serve >/dev/null 2>&1 &
  STARTED_OLLAMA=true
  for i in $(seq 1 30); do
    if curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    echo "ERROR: Ollama failed to start after 30s." >&2
    exit 1
  fi
  echo "Native Ollama started."
fi

# ── 4. Ensure models are pulled ─────────────────────────────────────────────
pull_if_missing() {
  local model="$1"
  if ! ollama list 2>/dev/null | grep -q "$model"; then
    echo "Pulling model: ${model}"
    ollama pull "$model"
  else
    echo "Model ready: ${model}"
  fi
}

pull_if_missing "$MODEL"
pull_if_missing "$EMBED_MODEL"

# ── 5. Ensure ChromaDB is running ──────────────────────────────────────────
if ! curl -sf "http://localhost:8000/api/v2/heartbeat" >/dev/null 2>&1 \
  && ! curl -sf "http://localhost:8000/api/v1/heartbeat" >/dev/null 2>&1; then
  echo "Starting ChromaDB via Docker..."
  cd "$REPO_ROOT"
  docker compose up -d chromadb
  for i in $(seq 1 30); do
    if curl -sf "http://localhost:8000/api/v2/heartbeat" >/dev/null 2>&1 \
      || curl -sf "http://localhost:8000/api/v1/heartbeat" >/dev/null 2>&1; then
      echo "ChromaDB ready."
      break
    fi
    sleep 1
  done
fi

# ── 6. Verify GPU is in use ────────────────────────────────────────────────
echo ""
echo "--- Ollama status ---"
ollama ps 2>/dev/null || true
echo "---------------------"
echo ""

# ── 7. Run the scraper ─────────────────────────────────────────────────────
echo "Starting scraper with native Ollama (model=${MODEL})..."
cd "$REPO_ROOT"
exec .venv/bin/python -m web_scraper scrape "$@" \
  --model "$MODEL" --embed-model "$EMBED_MODEL"
