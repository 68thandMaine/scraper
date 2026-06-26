#!/bin/sh
set -e

# By default do not block on Ollama/ChromaDB. Compose depends_on handles ordering.
# Set WAIT_FOR_SERVICES=true to poll until both are reachable.
if [ "${WAIT_FOR_SERVICES:-false}" = "true" ]; then
  OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
  CHROMA_HOST="${CHROMA_HOST:-chromadb}"
  CHROMA_PORT="${CHROMA_PORT:-8000}"

  echo "WAIT_FOR_SERVICES=true: polling Ollama at ${OLLAMA_HOST}..."
  for i in $(seq 1 120); do
    if curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
      echo "Ollama ready (attempt ${i})"
      break
    fi
    sleep 2
  done

  echo "WAIT_FOR_SERVICES=true: polling ChromaDB at ${CHROMA_HOST}:${CHROMA_PORT}..."
  for i in $(seq 1 60); do
    if curl -sf "http://${CHROMA_HOST}:${CHROMA_PORT}/api/v2/heartbeat" >/dev/null 2>&1 \
      || curl -sf "http://${CHROMA_HOST}:${CHROMA_PORT}/api/v1/heartbeat" >/dev/null 2>&1; then
      echo "ChromaDB ready (attempt ${i})"
      break
    fi
    sleep 2
  done
else
  echo "Skipping service wait (WAIT_FOR_SERVICES=false). Starting scraper immediately."
fi

# Inject corporate CA certs (e.g. Zscaler) if /certs contains any .pem or .crt files.
_certs=$(find /certs -maxdepth 1 \( -name '*.pem' -o -name '*.crt' \) 2>/dev/null | head -1)
if [ -n "${_certs}" ]; then
  _certifi=$(python -c 'import certifi; print(certifi.where())')
  cat "${_certifi}" /certs/*.pem /certs/*.crt > /tmp/ca-bundle.pem 2>/dev/null || true
  export REQUESTS_CA_BUNDLE=/tmp/ca-bundle.pem
  export SSL_CERT_FILE=/tmp/ca-bundle.pem
  export CURL_CA_BUNDLE=/tmp/ca-bundle.pem
  echo "Loaded custom CA certs from /certs into /tmp/ca-bundle.pem"
fi

mkdir -p "${SCRAPED_DATA_DIR:-/app/scraped_data}"

exec python -m web_scraper "$@"
