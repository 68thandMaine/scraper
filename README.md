# Web Scraper Agent

A Dockerized web scraper that crawls sites, cleans each page with a local
**Ollama** model, and uses **ChromaDB** vector memory to detect duplicates and
consolidate overlapping documentation.

**Documentation:** run `make docs` or see the [docs site](docs/README.md).

## Features

- Crawl websites and follow internal links (subdomain + path filters)
- Agent pipeline: clean, embed, recall, decide, store
- ChromaDB vector memory for similarity and consolidation
- Fully Dockerized (Ollama + ChromaDB + scraper-agent)
- Legacy `--no-agent` mode for direct HTML-to-text output
- CLI, tests, and Docusaurus documentation

## Quick start (Docker)

```bash
# Start Ollama and ChromaDB (first run pulls qwen2.5:3b + nomic-embed-text)
docker compose up -d ollama chromadb

# Scrape with the agent
docker compose --profile scrape run --rm scraper-agent scrape \
  https://example.com/docs \
  --output-dir /app/scraped_data \
  --max-files 50
```

Output is written to `./scraped_data/` on the host.

## Installation (local)

```bash
pip install -r requirements.txt
pip install -e .
cp .env.example .env
```

## Usage

```bash
# Agent mode (default) -- requires Ollama + ChromaDB
python -m web_scraper scrape https://example.com

# Legacy direct save (no LLM)
python -m web_scraper scrape https://example.com --no-agent

# Options
python -m web_scraper scrape https://example.com \
  --output-dir ./scraped_data \
  --max-files 100 \
  --model qwen2.5:3b \
  --similarity-threshold 0.85
```

### Faster inference on Mac (recommended)

Run Ollama natively (Metal/GPU), keep ChromaDB in Docker, and point the scraper at the host:

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
docker compose up -d chromadb

OLLAMA_HOST=http://host.docker.internal:11434 \
docker compose --profile scrape run --rm scraper-agent scrape \
  "https://code.claude.com/docs/en/memory" \
  --output-dir /app/scraped_data \
  --subdomain code.claude.com/docs/en -t 60 -m 5 -y
```

## Makefile

| Command | Description |
|---------|-------------|
| `make install` | Install Python dependencies |
| `make test` | Run pytest with coverage |
| `make docker-up` | Start Ollama + ChromaDB |
| `make docker-scrape URL=...` | Run scrape in Docker |
| `make docs` | Start Docusaurus locally |

## Project structure

```
scraper-main/
├── web_scraper/
│   ├── agent.py          # Ollama + ChromaDB agent pipeline
│   ├── prompts.py        # LLM prompt templates
│   ├── scraper.py        # Crawler
│   └── cli.py            # CLI
├── docker-compose.yml
├── Dockerfile
├── docs/                 # Docusaurus documentation site
├── scraped_data/         # Default agent output (gitignored)
└── tests/
```

## Development

```bash
make test
make lint
make format
```

## Environment

See [.env.example](.env.example) for `OLLAMA_HOST`, `OLLAMA_MODEL` (default
`qwen2.5:3b`), `OLLAMA_EMBED_MODEL`, `MAX_LLM_INPUT_CHARS`, `CHROMA_HOST`, and
`SIMILARITY_THRESHOLD`.
