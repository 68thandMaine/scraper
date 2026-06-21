---
sidebar_position: 1
sidebar_label: Introduction
---

# Web Scraper Agent

**Web Scraper Agent** is a Dockerized web scraper that crawls documentation
sites, cleans each page with a local **Ollama** model, and uses **ChromaDB**
vector memory to detect duplicates and consolidate overlapping content.

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
| `scraper-agent` | Python crawler + Ollama agent pipeline |
| `ollama` | Local LLM for cleaning and decisions (`qwen2.5:3b`) |
| `chromadb` | Vector memory for similarity search |

## Documentation

- [Getting Started](./getting-started) -- run the stack with Docker
- [Architecture](./category/architecture) -- how the services fit together
- [Configuration](./category/configuration) -- env vars and CLI flags
- [Concepts](./category/concepts) -- consolidation logic and legacy mode
