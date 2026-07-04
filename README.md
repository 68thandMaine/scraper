# Web Scraper Agent

A web scraper for macOS that crawls sites, cleans each page with a local
**Ollama** model on **Apple Metal (GPU)**, and uses **ChromaDB** vector memory
to detect duplicates and consolidate overlapping documentation.

**Documentation:** run `make docs` or see the [docs site](docs/README.md).

## Recommended setup (Mac, bare-metal GPU)

Run **Ollama natively** so inference uses Metal. Keep **ChromaDB in Docker**
for persistence. Run the **Python scraper on the host** — no GPU work inside
containers.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Ollama (host)  │◄────│  web_scraper     │────►│ ChromaDB (Docker)│
│  Metal / GPU    │     │  python -m ...   │     │  localhost:8000  │
│  localhost:11434│     └──────────────────┘     └─────────────────┘
└─────────────────┘
```

### Prerequisites

- macOS on Apple Silicon (M1/M2/M3/M4)
- [Homebrew](https://brew.sh)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ChromaDB only)
- Python 3.11+ and a project virtualenv

16 GB RAM is recommended for `qwen2.5:3b` plus ChromaDB. The default model is
`qwen2.5:1.5b`, which is faster on GPU with little quality loss for this
pipeline.

### One-time install

```bash
# Ollama (Metal GPU)
brew install ollama

# Python deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Optional: copy defaults you may want to override later
cp .env.example .env
```

Pull models once (the helper script below also pulls if missing):

```bash
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text
```

### Quick start

From the repo root with `.venv` created and Docker Desktop running:

```bash
make native-scrape URL="https://example.com/docs" ARGS="-y --max-files 50"
```

Or use the script directly:

```bash
./scripts/scrape-native.sh https://example.com/docs \
  -y \
  --output-dir ./scraped_data \
  --max-files 50
```

`scrape-native.sh` will:

1. Use native Ollama when `ollama` is on your PATH (Metal GPU)
2. Stop the Docker `scraper-ollama` container if it is holding port 11434
3. Start `ollama serve` if nothing is listening on 11434
4. Pull missing models
5. Start ChromaDB via Docker if it is not already up
6. Run the scraper with `.venv/bin/python`

Output is written to `./scraped_data/` by default (override with `--output-dir`).

### Verify services

```bash
curl http://localhost:11434/api/tags    # native Ollama
curl http://localhost:8000/api/v2/heartbeat  # ChromaDB in Docker
ollama ps                                 # confirm a model is loaded on GPU
```

### Example scrape

```bash
./scripts/scrape-native.sh \
  "https://code.claude.com/docs/en/memory" \
  -y \
  --subdomain code.claude.com/docs/en \
  --timeout 60 \
  --max-files 5
```

### Common flags

```bash
# Agent mode (default) — Ollama + ChromaDB required
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
  --model qwen2.5:3b \
  --embed-model nomic-embed-text \
  --similarity-threshold 0.85
```

When running `python -m web_scraper` directly, Ollama defaults to
`http://localhost:11434` and ChromaDB to `localhost:8000`. The Python CLI does
not auto-load a `.env` file; export variables or pass CLI flags instead.

## Features

- Crawl websites and follow internal links (subdomain + path filters)
- Agent pipeline: clean, embed, recall, decide, store
- ChromaDB vector memory for similarity and consolidation
- Native Mac GPU inference via Ollama (Metal)
- Legacy `--no-agent` mode for direct HTML-to-text output
- CLI, tests, and Docusaurus documentation

## Makefile

| Command | Description |
|---------|-------------|
| `make install` | Install Python dependencies |
| `make native-scrape URL=... ARGS="..."` | Scrape with native Ollama (Metal) + Docker ChromaDB |
| `make docker-up` | Start ChromaDB only (or Ollama + ChromaDB if you use all-Docker mode) |
| `make docker-scrape URL=...` | Run scraper inside Docker (see below) |
| `make test` | Run pytest with coverage |
| `make docs` | Start Docusaurus locally |

## Alternative: all-Docker (CPU Ollama on Mac)

If you do not install Ollama via Homebrew, everything can run in Docker.
Ollama inside Docker on macOS does **not** use Metal; prefer the native setup
above for speed.

```bash
docker compose up -d ollama chromadb

docker compose --profile scrape run --rm scraper-agent scrape \
  https://example.com/docs \
  --output-dir /app/scraped_data \
  --max-files 50
```

**Hybrid:** scraper in Docker, Ollama on the host (GPU):

```bash
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text
docker compose up -d chromadb

OLLAMA_HOST=http://host.docker.internal:11434 \
docker compose --profile scrape run --rm scraper-agent scrape \
  "https://example.com/docs" \
  --output-dir /app/scraped_data \
  -y
```

For Docker Compose, copy `.env.example` to `.env` to override
`OLLAMA_HOST`, models, and thresholds without inline env vars.

## Project structure

```
scraper-main/
├── web_scraper/
│   ├── agent.py          # Ollama + ChromaDB agent pipeline
│   ├── prompts.py        # LLM prompt templates
│   ├── scraper.py        # Crawler
│   └── cli.py            # CLI
├── scripts/
│   └── scrape-native.sh  # Mac GPU quick path
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

See [.env.example](.env.example) for optional overrides: `OLLAMA_MODEL`,
`OLLAMA_EMBED_MODEL`, `MAX_LLM_INPUT_CHARS`, `CHROMA_HOST`, and
`SIMILARITY_THRESHOLD`. A `.env` file is optional; Docker Compose reads it
for `${VAR}` substitution. Native `python -m web_scraper` uses built-in
defaults unless you `export` variables or pass CLI flags.
