---
sidebar_position: 2
sidebar_label: CLI Reference
description: Command-line flags for the scrape command.
---

# CLI Reference

## scrape

```bash
python -m web_scraper scrape URL [OPTIONS]
```

### Crawl options

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output-dir` | `./scraped_docs/scraped_data` | Output directory |
| `-m, --max-files` | `300` | Max pages to process |
| `-d, --delay` | `0.5` | Seconds between requests |
| `-t, --timeout` | `10` | HTTP timeout (seconds) |
| `--include-external` | off | Follow external links (host-filtered) |
| `-s, --subdomain` | start URL host | Restrict to host |
| `-p, --path-prefix` | none | Restrict to path prefix |
| `-y, --yes` | off | Overwrite non-empty output dir |
| `--user-agent` | `WebScraper/2.0` | HTTP User-Agent |
| `--use-browser` | off | Use Playwright per page |

### Agent options

| Flag | Default | Description |
|------|---------|-------------|
| `--agent / --no-agent` | `--agent` | Enable Ollama agent pipeline |
| `--model` | `OLLAMA_MODEL` | Generation model |
| `--embed-model` | `OLLAMA_EMBED_MODEL` | Embedding model |
| `--similarity-threshold` | `0.85` | Cosine similarity for recall |

### Examples

```bash
# Docker (agent on by default)
docker compose --profile scrape run --rm scraper-agent scrape \
  https://docs.example.com -o /app/scraped_data -m 100

# Local legacy mode (no LLM)
python -m web_scraper scrape https://example.com --no-agent

# Local with agent
python -m web_scraper scrape https://example.com \
  --model qwen2.5:3b --similarity-threshold 0.9
```

## Other commands

| Command | Description |
|---------|-------------|
| `extract-urls` | Parse links from HTML file or stdin |
| `discover-urls` | Extract links via Playwright |
| `validate` | Validate a URL |
| `stats` | Directory statistics for `.txt` files |
