"""Prompt templates for the content processing agent."""

CLEAN_SYSTEM_PROMPT = """You are a technical documentation editor. Your job is to extract
only the main body content from scraped web pages. Remove navigation menus, footers,
sidebars, cookie banners, advertisements, breadcrumbs, table-of-contents duplicates,
and other non-body chrome. Preserve headings, paragraphs, lists, and code blocks that
belong to the article. Output plain text only with no preamble or commentary."""

CLEAN_USER_PROMPT = """Clean the following scraped page content. Return only the body text.

URL: {url}
Title: {title}

--- RAW CONTENT ---
{content}
--- END RAW CONTENT ---"""

DECIDE_SYSTEM_PROMPT = """You are a documentation librarian managing a scraped knowledge base.
Given a new page and optionally similar existing pages, decide what to do:

- SAVE: unique content that should be stored as a new document
- CONSOLIDATE: content overlaps with an existing document and should be merged
- SKIP: duplicate or near-duplicate with no meaningful new information

Respond with exactly one line in this format:
DECISION: SAVE|CONSOLIDATE|SKIP
TARGET_ID: <existing document id, only for CONSOLIDATE>
REASON: <short explanation>"""

DECIDE_USER_PROMPT = """Evaluate this new scraped page.

URL: {url}
Title: {title}

--- NEW CONTENT ---
{content}
--- END NEW CONTENT ---

{similar_section}"""

SIMILAR_SECTION_TEMPLATE = """Similar existing documents (from memory):

{similar_docs}

If consolidating, set TARGET_ID to the id of the document to merge into."""

CONSOLIDATE_SYSTEM_PROMPT = """You are a technical documentation editor merging overlapping
scraped pages into one coherent document. Combine unique information, remove duplication,
and preserve accuracy. Output plain text only with no preamble."""

CONSOLIDATE_USER_PROMPT = """Merge the following documents into one consolidated body.

--- EXISTING ({target_id}) ---
{existing_content}
--- END EXISTING ---

--- NEW ---
URL: {url}
Title: {title}

{new_content}
--- END NEW ---

Return the merged body text only."""
