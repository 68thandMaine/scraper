# Web Scraper Agent

A web scraper for macOS that crawls sites, cleans each page with a local LLM
served through **llama.cpp** (`llama-server`) on **Apple Metal (GPU)**, and
uses **ChromaDB** vector memory to detect duplicates and consolidate
overlapping documentation. `llama-server` exposes an OpenAI-compatible API
(`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`). Environment
variables keep the `OLLAMA_*` names for backward compatibility, but they now
point at `llama-server`, not Ollama.

**Documentation:** run `make docs` or see the [docs site](docs/README.md).

## Recommended setup (Mac, bare-metal GPU)

Run **two `llama-server` processes natively** — one for generation, one for
embeddings — so inference uses Metal. Keep **ChromaDB in Docker** for
persistence. Run the **Python scraper on the host** — no GPU work inside
containers.

```
┌─────────────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ llama-server (generate) │◄────│  web_scraper     │────►│ ChromaDB (Docker)│
│ Metal / GPU              │     │  python -m ...   │     │  localhost:8000  │
│ localhost:8081           │     └────────┬─────────┘     └──────────────────┘
└─────────────────────────┘              │
┌─────────────────────────┐              │
│ llama-server (embed)    │◄─────────────┘
│ Metal / GPU              │
│ localhost:8080           │
└─────────────────────────┘
```

### Prerequisites

- macOS on Apple Silicon (M1/M2/M3/M4)
- [Homebrew](https://brew.sh)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ChromaDB only)
- Python 3.11+ and a project virtualenv
- `llama.cpp` built with Metal support, providing the `llama-server` binary

16 GB RAM is recommended for a small (1.5B-3B) GGUF generation model plus
ChromaDB. The defaults in [.env.example](.env.example) are `qwen`
(generation) and `nomic-embed-text` (embeddings) — these are the `--alias`
names each `llama-server` process must report.

### One-time install

```bash
# llama.cpp (Metal GPU) — provides the llama-server binary
brew install llama.cpp

# Python deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Optional: copy defaults you may want to override later
cp .env.example .env
```

Download (or convert) GGUF files for your generation and embedding models,
then start one `llama-server` per role. The `--alias` passed to each server
is the model ID the scraper looks up over `/v1/models`, so it must match
`OLLAMA_MODEL` / `OLLAMA_EMBED_MODEL`:

```bash
# Generation server on port 8081 (matches OLLAMA_HOST in .env.example)
llama-server -m /path/to/qwen.gguf --alias qwen --port 8081 --n-gpu-layers 999

# Embedding server on port 8080 (matches OLLAMA_EMBED_HOST in .env.example)
llama-server -m /path/to/nomic-embed-text.gguf --alias nomic-embed-text \
  --port 8080 --embedding --n-gpu-layers 999
```

### Quick start

With both `llama-server` processes running and Docker Desktop up:

```bash
docker compose up -d chromadb

source .venv/bin/activate
python -m web_scraper scrape https://example.com/docs -y --max-files 50
```

Output is written to `./scraped_data/` by default (override with `--output-dir`).

### Verify services

```bash
curl http://localhost:8081/v1/models         # generation llama-server
curl http://localhost:8080/v1/models         # embedding llama-server
curl http://localhost:8000/api/v2/heartbeat  # ChromaDB in Docker
```

### Example scrape

```bash
python -m web_scraper scrape \
  "https://code.claude.com/docs/en/memory" \
  -y \
  --subdomain code.claude.com/docs/en \
  --timeout 60 \
  --max-files 5
```

### Common flags

```bash
# Agent mode (default) — llama-server + ChromaDB required
python -m web_scraper scrape https://example.com -y

# Skip LLM cleaning (~33% faster; still embeds and dedupes)
python -m web_scraper scrape https://example.com -y --no-llm-clean

# JS-rendered sites
python -m web_scraper scrape https://example.com -y --use-browser

# Legacy direct HTML-to-text (no LLM, no ChromaDB)
python -m web_scraper scrape https://example.com --no-agent -y

# Tune models and dedup threshold
python -m web_scraper scrape https://example.com \
  -y \
  --model qwen \
  --embed-model nomic-embed-text \
  --similarity-threshold 0.85
```

The Python CLI does not auto-load a `.env` file. Without exported
environment variables it uses generation on `http://localhost:8081` and
embeddings on `http://localhost:8080`; export the variables from
`.env.example` (or run through `make`/Docker Compose, which load `.env`) to
target the two-port `llama-server` setup described above.

### Generation timeouts

The scraper requests streamed tokens and disables thinking for its cleaning
and deduplication calls using `chat_template_kwargs.enable_thinking=false`.
`OLLAMA_TIMEOUT` is the read inactivity timeout: a long generation can finish
as long as tokens keep arriving. Prompt processing and queue waits must still
fit within that timeout. The default is 600 seconds.

Set `OLLAMA_MODEL` to the alias reported by `/v1/models` (for example, `hermes`
on an existing local server). Empty, interrupted, and token-limit-truncated
responses are treated as errors; the original page is preserved for retry.
If the output limit is reached, increase `OLLAMA_NUM_PREDICT` (for example,
4096 for longer pages). This does not change the input truncation limit or
guarantee full-site coverage.

## Features

- Crawl websites and follow internal links (subdomain + path filters)
- Agent pipeline: clean, embed, recall, decide, store
- ChromaDB vector memory for similarity and consolidation
- Native Mac GPU inference via llama.cpp (`llama-server`, Metal)
- Legacy `--no-agent` mode for direct HTML-to-text output
- CLI, tests, and Docusaurus documentation

## Makefile

| Command | Description |
|---------|-------------|
| `make install` | Install Python dependencies |
| `make native-scrape URL=... ARGS="..."` | Legacy Ollama-based native script (see `scripts/scrape-native.sh`); for the `llama-server` setup, use the manual Quick start steps above |
| `make docker-up` | Start ChromaDB via Docker (also starts the legacy `ollama` container defined in `docker-compose.yml`) |
| `make docker-scrape URL=...` | Run scraper inside Docker (see below) |
| `make test` | Run pytest with coverage |
| `make docs` | Start Docusaurus locally |

## Alternative: scraper in Docker, llama-server on host

If you prefer to run the scraper itself in Docker while still using
`llama-server` on the host for Metal GPU inference:

```bash
docker compose up -d chromadb

docker compose --profile scrape run --rm scraper-agent scrape \
  https://example.com/docs \
  --output-dir /app/scraped_data \
  --max-files 50
```

The `scraper-agent` service in `docker-compose.yml` defaults `OLLAMA_HOST`
and `OLLAMA_EMBED_HOST` to `http://host.docker.internal:8081` and
`http://host.docker.internal:8080`, so it reaches `llama-server` processes
running on the Mac host without extra configuration. Copy `.env.example` to
`.env` to override hosts, models, or thresholds without inline env vars.

## Project structure

```
scraper-main/
├── web_scraper/
│   ├── agent.py          # llama-server + ChromaDB agent pipeline
│   ├── prompts.py        # LLM prompt templates
│   ├── scraper.py        # Crawler
│   └── cli.py            # CLI
├── scripts/
│   └── scrape-native.sh  # Legacy Ollama-based Mac GPU quick path
├── docker-compose.yml
├── Dockerfile
├── docs/                 # Docusaurus documentation site
├── scraped_data/         # Default agent output (gitignored)
└── tests/
```

## Development

```bash
source .venv/bin/activate
make test
make lint
make format
```

## Environment

See [.env.example](.env.example) for optional overrides. Variable names keep
the `OLLAMA_*` prefix for backward compatibility even though they now
configure `llama-server`:

- `OLLAMA_HOST` — generation `llama-server` base URL (default `http://localhost:8081` in `.env.example`)
- `OLLAMA_MODEL` — generation model alias (default `qwen`)
- `OLLAMA_EMBED_HOST` — embedding `llama-server` base URL (default `http://localhost:8080` in `.env.example`); leave blank to share `OLLAMA_HOST`
- `OLLAMA_EMBED_MODEL` — embedding model alias (default `nomic-embed-text`)
- `MAX_LLM_INPUT_CHARS`, `MAX_EMBED_INPUT_CHARS` — input truncation limits
- `CHROMA_HOST`, `CHROMA_PORT` — ChromaDB connection (Docker default `localhost:8000`)
- `SIMILARITY_THRESHOLD` — dedup/consolidation threshold

A `.env` file is optional; Docker Compose reads it for `${VAR}` substitution.
Native `python -m web_scraper` uses built-in defaults unless you `export`
variables or pass CLI flags.
