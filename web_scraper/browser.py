"""Browser-based fetching for JavaScript-rendered pages (e.g. cursor.com/docs)."""

import logging
from typing import List, Optional

from .utils import (
    get_domain,
    normalize_url,
    url_path_under_prefix,
)

logger = logging.getLogger(__name__)


def _get_playwright():
    """Import Playwright; raise a clear error if not installed."""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError as e:
        raise ImportError(
            "Playwright is required for browser-based scraping. "
            "Install with: pip install playwright && playwright install chromium"
        ) from e


def fetch_with_browser(
    url: str,
    wait_seconds: float = 2.0,
    wait_selector: Optional[str] = None,
    timeout_ms: int = 30_000,
) -> str:
    """
    Load a URL in a headless browser and return the rendered HTML.

    Use this for SPAs where content and links are added by JavaScript.
    The page is loaded, then we wait for `wait_seconds` (and optionally
    for an element matching `wait_selector`) before capturing the HTML.

    Args:
        url: Full URL to load.
        wait_seconds: Seconds to wait after load for JS to render (default 2).
        wait_selector: Optional CSS selector to wait for (e.g. "nav a").
        timeout_ms: Page load timeout in milliseconds.

    Returns:
        Rendered HTML as string.
    """
    sync_playwright = _get_playwright()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            if wait_seconds > 0:
                page.wait_for_timeout(int(wait_seconds * 1000))
            html = page.content()
            return html
        finally:
            browser.close()


def extract_links_from_page(
    url: str,
    base_url: Optional[str] = None,
    path_prefix: Optional[str] = None,
    wait_seconds: float = 2.0,
    wait_selector: Optional[str] = None,
) -> List[str]:
    """
    Load a URL in a headless browser and extract all same-origin <a href> links.

    Useful for doc sites like cursor.com/docs where the sidebar links are
    rendered by JavaScript and not present in the initial HTML.

    Args:
        url: Full URL to load (e.g. https://cursor.com/docs).
        base_url: Base URL for resolving relative hrefs; defaults to url.
        path_prefix: If set, only return URLs whose path starts with this (e.g. "/docs").
        wait_seconds: Seconds to wait after load for links to appear.
        wait_selector: Optional CSS selector to wait for before extracting links.

    Returns:
        Sorted list of unique absolute URLs (same domain only, optional path filter).
    """
    from bs4 import BeautifulSoup

    base = base_url or url
    html = fetch_with_browser(
        url,
        wait_seconds=wait_seconds,
        wait_selector=wait_selector,
    )
    soup = BeautifulSoup(html, "html.parser")
    base_domain = get_domain(base)
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href or href.startswith("#") or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        normalized = normalize_url(href, base)
        if get_domain(normalized) != base_domain:
            continue
        if path_prefix and not url_path_under_prefix(normalized, path_prefix):
            continue
        seen.add(normalized)

    return sorted(seen)
