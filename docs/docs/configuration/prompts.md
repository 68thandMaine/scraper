---
sidebar_position: 3
sidebar_label: Prompts
description: Tune agent prompts for cleaning and consolidation.
---

# Prompt Tuning

All prompts are defined in `web_scraper/prompts.py` as plain string templates.

## CLEAN prompts

- `CLEAN_SYSTEM_PROMPT` -- instructs the model to strip chrome and keep body
  content only.
- `CLEAN_USER_PROMPT` -- includes URL, title, and raw scraped text.

Adjust these if your target sites use unusual layouts (e.g. heavy tab panels or
embedded widgets).

## DECIDE prompts

- `DECIDE_SYSTEM_PROMPT` -- defines `SAVE`, `CONSOLIDATE`, and `SKIP` and the
  required response format.
- `DECIDE_USER_PROMPT` -- includes cleaned content and a similar-documents
  section from ChromaDB.

The agent parses responses with a regex expecting:

```text
DECISION: SAVE|CONSOLIDATE|SKIP
TARGET_ID: <id>
REASON: <text>
```

If parsing fails, the agent defaults to **SAVE**.

## CONSOLIDATE prompts

- `CONSOLIDATE_SYSTEM_PROMPT` -- merge overlapping documents.
- `CONSOLIDATE_USER_PROMPT` -- existing + new content blocks.

## Tips

- Keep system prompts short and imperative for small models like `qwen2.5:3b`.
- Large pages are truncated to `MAX_LLM_INPUT_CHARS` (default 10000) before CLEAN.
- Lower `SIMILARITY_THRESHOLD` to surface more consolidation candidates.
- Test prompt changes with `pytest tests/test_agent.py` (mocked Ollama).
