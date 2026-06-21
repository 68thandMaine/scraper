---
sidebar_position: 2
sidebar_label: Backward Compatibility
description: Legacy scraping without the Ollama agent.
---

# Backward Compatibility

The original scraper behavior is preserved behind `--no-agent`.

## Legacy mode

```bash
python -m web_scraper scrape https://example.com --no-agent
```

In legacy mode:

- No Ollama or ChromaDB connection is required.
- Pages are saved directly after HTML text extraction.
- No cleaning, embedding, or consolidation runs.

## Default behavior

The CLI defaults to `--agent` (agent enabled). Docker runs use the agent unless
you pass `--no-agent` to the scrape command.

## API compatibility

`WebScraper.scrape_website()` accepts an optional `agent` parameter:

- `agent=None` -- direct file save (legacy).
- `agent=ContentAgent(...)` -- agent pipeline per page.

`iter_scraped_pages()` yields raw scraped dicts for custom integrations.

## Tests

Existing scraper tests run without an agent. Agent tests mock Ollama and
ChromaDB in `tests/test_agent.py`.
