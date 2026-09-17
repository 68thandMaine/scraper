---
sidebar_position: 1
sidebar_label: Introduction
---

# Web Scraper Agent

**Web Scraper Agent** is a Dockerized web scraper that crawls documentation
sites, cleans each page with a local generation model served by
**llama-server**, and uses **ChromaDB** vector memory to detect duplicates and
consolidate overlapping content.

## What it does

1. Crawls a site starting from a URL (with subdomain and path filters).
2. Extracts raw text from each HTML page.
3. Passes each page to a local agent that removes navigation, footers, and
   other non-body chrome.
4. Compares the page against previously scraped documents using embeddings.
5. Decides to **save**, **consolidate**, or **skip** each page.
6. Writes cleaned `.txt` files to `scraped_data/`.

## Stack

| Service | Role |
|---------|------|
| `scraper-agent` | Python crawler + local model-server agent pipeline |
| `llama-server` (generation) | Local model for cleaning and decisions |
| `llama-server` (embedding) | Local model for vector embeddings |
| `chromadb` | Vector memory for similarity search |

The Compose file also retains a bundled `ollama` service as a compatibility
path. The current default configuration uses separate generation and embedding
`llama-server` endpoints; see [Getting Started](./getting-started) for the
required health checks.

## Documentation

- [Getting Started](./getting-started) -- run the stack with Docker
- [Architecture](./category/architecture) -- how the services fit together
- [Configuration](./category/configuration) -- env vars and CLI flags
- [Concepts](./category/concepts) -- consolidation logic and legacy mode
