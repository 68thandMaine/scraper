---
sidebar_position: 2
sidebar_label: Getting Started
description: Run the scraper agent stack with Docker Compose.
---

# Getting Started

## Prerequisites

- Docker Desktop (Apple Silicon supported)
- 16 GB RAM recommended for `qwen2.5:3b` + ChromaDB on M1/M2 Macs

## Start infrastructure

From the repository root:

```bash
docker compose up -d ollama chromadb
```

On first run, Ollama pulls `qwen2.5:3b` and `nomic-embed-text`. This can take
several minutes.

For faster inference on a Mac, run Ollama on the host (Metal/GPU) and set
`OLLAMA_HOST=http://host.docker.internal:11434` when running the scraper in
Docker. See the root [README](https://ghe.megaleo.com/chris-rudnicky/scraper)
for an example command.

Check services:

```bash
docker compose ps
curl http://localhost:11434/api/tags
curl http://localhost:8000/api/v1/heartbeat
```

## Run a scrape

```bash
docker compose --profile scrape run --rm scraper-agent scrape \
  https://example.com/docs \
  --output-dir /app/scraped_data \
  --max-files 50
```

Output appears in `./scraped_data/` on the host (bind-mounted).

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

With the agent, Ollama and ChromaDB must be reachable (see `.env.example`).

## View documentation locally

```bash
make docs
```

Or:

```bash
docker compose --profile docs up docs
```

Open http://localhost:3000
