---
sidebar_position: 2
sidebar_label: Getting Started
description: Run the scraper agent stack with Docker Compose.
---

# Getting Started

## Prerequisites

- Docker Desktop (Apple Silicon supported)
- A local generation and embedding model served by `llama-server`
- 16 GB RAM recommended for local inference plus ChromaDB on M1/M2 Macs

## Start infrastructure

The current agent configuration uses two OpenAI-compatible `llama-server`
processes: one for generation and one for embeddings. Start them on the host
with model aliases that match the scraper configuration:

```bash
# Generation server
llama-server -m /path/to/generation.gguf --alias qwen --port 8081 --n-gpu-layers 999

# Embedding server
llama-server -m /path/to/nomic-embed-text.gguf --alias nomic-embed-text \
  --port 8080 --embedding --n-gpu-layers 999
```

Start ChromaDB from the repository root:

```bash
docker compose up -d chromadb
```

Check services:

```bash
curl http://localhost:8081/v1/models         # generation server
curl http://localhost:8080/v1/models         # embedding server
curl http://localhost:8000/api/v2/heartbeat  # ChromaDB
```

The Compose file retains a bundled `ollama` service for compatibility. It is
not the current default endpoint for the agent; use the hostnames and model
aliases in [Docker Configuration](./configuration/docker) if you intentionally
run the bundled service instead.

## Run a scrape

```bash
docker compose --profile scrape run --rm scraper-agent scrape \
  https://example.com/docs \
  --output-dir /app/scraped_data \
  --max-files 50
```

Output appears in `./scraped_data/` on the host (bind-mounted).

## Run a bounded research corpus

For the six-source research collection (Kind, Gitea, Flox, Colima, LocalStack,
and Flux), use the resumable research script rather than the single-site CLI.
It stores complete source records and selected AI notes together in one output
directory. The file-count guard requires that directory to stay below 300 files
(`files < 300`).

From the repository root, start or resume the crawl with:

```bash
PYTHONPATH=. .venv/bin/python -u scripts/research_docs.py \
  --output scraped_docs/scylla-lab-ai
```

The script's AI pass uses the generation endpoint in `OLLAMA_HOST` (the
default is `http://localhost:8081`) and currently requests the `hermes` model
alias. Verify that the generation `llama-server` reports that alias before
starting:

```bash
curl http://localhost:8081/v1/models
```

The research script does not use ChromaDB or the embedding endpoint. The
standard agent CLI still requires ChromaDB and, when configured with separate
servers, uses `OLLAMA_EMBED_HOST` (the default is
`http://localhost:8080`) for embeddings.

After the source crawl reaches `finished` or `finished_with_gaps`, resume only
the unfinished AI notes with:

```bash
PYTHONPATH=. OLLAMA_NUM_PREDICT=2048 .venv/bin/python -u scripts/research_docs.py \
  --output scraped_docs/scylla-lab-ai --ai-only
```

Run the periodic on-disk audit in a second terminal:

```bash
PYTHONPATH=. .venv/bin/python -u scripts/watch_research_docs.py \
  scraped_docs/scylla-lab-ai
```

The audit compares source ledgers, readable bundles, checksums, status counts,
and the file limit. Keep the research process and its generation server
running until the status reaches `finished`. If the process stops during the
crawl, rerun the first command; if the crawl is complete, use `--ai-only`.

The output directory contains full `<source>.pages.jsonl` records, readable
`<source>.source.md` bundles, and bounded `<source>.ai.jsonl`/`<source>.ai.md`
research notes. AI errors are recorded in the JSONL status and do not remove
the saved source page. To rebuild readable text after an extractor fix while
preserving captured HTML, run:

```bash
PYTHONPATH=. .venv/bin/python -u scripts/research_docs.py \
  --output scraped_docs/scylla-lab-ai --rerender-only
```

## Makefile shortcuts

```bash
make docker-up
make docker-scrape URL=https://example.com/docs ARGS="--max-files 20"
```

## Local development (no Docker)

Install dependencies and run without the agent (legacy direct save):

```bash
pip install -r requirements.txt
pip install -e .
python -m web_scraper scrape https://example.com --no-agent
```

With the agent, both model-server endpoints and ChromaDB must be reachable (see
`.env.example`).

## View documentation locally

```bash
make docs
```

Or:

```bash
docker compose --profile docs up docs
```

Open http://localhost:3000
