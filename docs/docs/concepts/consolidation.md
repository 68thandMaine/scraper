---
sidebar_position: 1
sidebar_label: Consolidation
description: How the agent decides to save, merge, or skip documents.
---

# Consolidation Logic

The agent avoids duplicate and overlapping documentation in `scraped_data/`.

## When documents are similar

1. ChromaDB returns nearest neighbors by embedding distance.
2. Neighbors with similarity `>= SIMILARITY_THRESHOLD` are listed in the
   **DECIDE** prompt.
3. Ollama chooses **CONSOLIDATE** with a `TARGET_ID` or **SAVE** if topics
   differ despite surface similarity.

## Consolidate action

1. Load existing body from ChromaDB or the `.txt` file on disk.
2. Run **CONSOLIDATE** prompt with existing + new content.
3. Overwrite the target `.txt` file with merged text.
4. Upsert the new embedding and metadata in ChromaDB.

## Skip action

Used when the new page adds no meaningful information (exact duplicate or
empty body after cleaning). Nothing is written; stats increment `skipped`.

## Output format

Saved files keep the original format:

```text
URL: https://example.com/page
Title: Page Title
--------------------------------------------------

<body text>
```

Filenames use `NNN_Sanitized_Title.txt` where `NNN` is a zero-padded index.
