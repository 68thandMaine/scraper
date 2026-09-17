---
sidebar_position: 1
sidebar_label: Docker
description: docker-compose services, volumes, and environment variables.
---

# Docker Configuration

## Services

| Service | Image / build | Ports | Profile |
|---------|---------------|-------|---------|
| `ollama` | `ollama/ollama` compatibility service | 11434 | default |
| `chromadb` | `chromadb/chroma` | 8000 | default |
| `scraper-agent` | `Dockerfile` | -- | `scrape` |
| `docs` | `node:20-alpine` | 3000 | `docs` |

## Volumes

| Volume | Purpose |
|--------|---------|
| `ollama_data` | Downloaded models |
| `chroma_data` | Vector index persistence |
| `./scraped_data` | Host bind mount for output `.txt` files |

## Current model-server setup

The current agent uses OpenAI-compatible `llama-server` endpoints. Run one
generation server and one embedding server on the host, then start ChromaDB:

```bash
docker compose up -d chromadb
```

The `scraper-agent` Compose defaults address those host processes as
`host.docker.internal:8081` and `host.docker.internal:8080`:

```text
OLLAMA_HOST=http://host.docker.internal:8081
OLLAMA_MODEL=qwen
OLLAMA_EMBED_HOST=http://host.docker.internal:8080
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_TIMEOUT=600
MAX_LLM_INPUT_CHARS=10000
MAX_EMBED_INPUT_CHARS=6000
OLLAMA_NUM_PREDICT=1024
CHROMA_HOST=chromadb
CHROMA_PORT=8000
SIMILARITY_THRESHOLD=0.85
SCRAPED_DATA_DIR=/app/scraped_data
```

The `OLLAMA_*` names are retained for compatibility. Generation uses
`/v1/chat/completions`; embeddings use `/v1/embeddings`. The model aliases must
be present in `/v1/models` on their respective servers.

## Bundled Ollama compatibility path

The bundled `ollama` service is still available and pulls its legacy default
models through `scripts/pull-model.sh`. To use it from `scraper-agent`, override
both endpoints so generation and embeddings use the Compose service:

```text
OLLAMA_HOST=http://ollama:11434
OLLAMA_EMBED_HOST=http://ollama:11434
```

Copy `.env.example` to `.env` to persist these overrides. The scraper container
also includes `extra_hosts` for `host.docker.internal` when using host-based
`llama-server` processes.

## Model pull

`scripts/pull-model.sh` is mounted as the bundled Ollama entrypoint. It starts
`ollama serve`, waits until ready, then pulls the configured generation and
embedding models. This path is separate from the host `llama-server` setup.

## Health checks

- **Generation server:** `curl http://localhost:8081/v1/models`
- **Embedding server:** `curl http://localhost:8080/v1/models`
- **ChromaDB:** `curl http://localhost:8000/api/v2/heartbeat`

When the bundled compatibility path is selected, check it with
`curl http://localhost:11434/api/tags` instead. Compose orders the declared
service dependencies; set `WAIT_FOR_SERVICES=true` when the container should
also poll its endpoints before invoking the CLI.
