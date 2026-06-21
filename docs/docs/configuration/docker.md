---
sidebar_position: 1
sidebar_label: Docker
description: docker-compose services, volumes, and environment variables.
---

# Docker Configuration

## Services

| Service | Image / build | Ports | Profile |
|---------|---------------|-------|---------|
| `ollama` | `ollama/ollama` | 11434 | default |
| `chromadb` | `chromadb/chroma` | 8000 | default |
| `scraper-agent` | `Dockerfile` | -- | `scrape` |
| `docs` | `node:20-alpine` | 3000 | `docs` |

## Volumes

| Volume | Purpose |
|--------|---------|
| `ollama_data` | Downloaded models |
| `chroma_data` | Vector index persistence |
| `./scraped_data` | Host bind mount for output `.txt` files |

## Environment variables

Copy `.env.example` to `.env` and adjust:

```bash
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_EMBED_MODEL=nomic-embed-text
MAX_LLM_INPUT_CHARS=10000
OLLAMA_NUM_PREDICT=2048
CHROMA_HOST=chromadb
CHROMA_PORT=8000
SIMILARITY_THRESHOLD=0.85
SCRAPED_DATA_DIR=/app/scraped_data
```

Inside `docker-compose.yml`, `scraper-agent` receives these automatically.

For Ollama on the Mac host (faster than CPU-only Docker Ollama):

```bash
OLLAMA_HOST=http://host.docker.internal:11434
```

`scraper-agent` includes `extra_hosts` for `host.docker.internal`.

## Model pull

`scripts/pull-model.sh` is mounted as the Ollama entrypoint. It starts
`ollama serve`, waits until ready, then pulls generation and embedding models.

## Health checks

- **Ollama:** `ollama list`
- **ChromaDB:** `curl /api/v1/heartbeat`

`scraper-agent` waits for both before running CLI commands.
