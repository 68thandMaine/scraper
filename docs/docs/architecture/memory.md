---
sidebar_position: 3
sidebar_label: Memory
description: ChromaDB vector store and embedding strategy.
---

# Vector Memory

`DocumentMemory` in `web_scraper/agent.py` wraps a ChromaDB HTTP client.

## Collection

- **Name:** `scraped_documents`
- **Distance:** cosine (`hnsw:space: cosine`)

## Stored fields

| Field | Description |
|-------|-------------|
| `id` | Filename stem, e.g. `003_API_Reference` |
| `document` | Cleaned body text |
| `embedding` | Vector from the configured embedding model server |
| `metadata` | `url`, `title`, `doc_id`, `timestamp`, `word_count` |

## Similarity

ChromaDB returns distances in `[0, 2]` for cosine space. The agent converts
to similarity as `1.0 - distance` and compares against
`SIMILARITY_THRESHOLD` (default `0.85`).

Documents above the threshold are included in the **DECIDE** prompt so the LLM
can choose consolidation vs. treating content as distinct.

The client calls the embedding server's OpenAI-compatible `/v1/embeddings`
endpoint. Inputs larger than `MAX_EMBED_INPUT_CHARS` (default `6000`) are
chunked and mean-pooled. If the server rejects a chunk because of its physical
context or batch limit, the client splits that chunk again and preserves the
full input; unrelated server errors remain errors.

## Persistence

ChromaDB data is stored in the `chroma_data` Docker volume and survives
container restarts.
