"""Core web scraping functionality."""

import logging
import time
from pathlib import Path

from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Set

if TYPE_CHECKING:
    from .agent import ContentAgent
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from .utils import (
    clean_filename,
    create_output_directory,
    extract_text_content,
    get_domain,
    get_internal_links,
    url_matches_netloc,
    url_path_under_prefix,
)


class WebScraper:
    """
    A comprehensive web scraper that extracts text content from websites.
    """

    def __init__(
        self,
        max_files: int = 300,
        delay: float = 0.5,
        timeout: int = 10,
        user_agent: str = "WebScraper/2.0",
        use_browser: bool = False,
    ) -> None:
        """
        Initialize the web scraper.

        Args:
            max_files: Maximum number of files to create
            delay: Delay between requests in seconds (default 0.5 to avoid rate limits)
            timeout: Request timeout in seconds
            user_agent: User agent string for requests
            use_browser: If True, fetch pages with Playwright for JS-rendered content
        """
        self.max_files = max_files
        self.delay = delay
        self.timeout = timeout
        self.user_agent = user_agent
        self.use_browser = use_browser

        # Setup session with headers
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        self.logger = logging.getLogger(__name__)

        # Track scraped URLs and content
        self.scraped_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        self.scraped_content: List[Dict[str, str]] = []

    def scrape_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Scrape a single URL and extract its content.

        Args:
            url: URL to scrape

        Returns:
            Dictionary with URL, title, and content, or None if failed
        """
        try:
            fetch_mode = "browser" if self.use_browser else "http"
            self.logger.info(
                "Fetching page (%s, timeout=%ds): %s",
                fetch_mode,
                self.timeout,
                url,
            )
            started = time.perf_counter()
            if self.use_browser:
                from .browser import fetch_with_browser
                html = fetch_with_browser(url, wait_seconds=2.0)
            else:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                html = response.text
            self.logger.info(
                "Fetch complete in %.1fs: %s (%d bytes html)",
                time.perf_counter() - started,
                url,
                len(html),
            )

            text_content = extract_text_content(html)
            self.logger.info(
                "Extracted %d chars text from %s",
                len(text_content),
                url,
            )

            if not text_content.strip():
                self.logger.warning("No text content found for: %s", url)
                return None

            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text().strip() if title_tag else ""

            if not title:
                parsed_url = urlparse(url)
                title = parsed_url.path.strip("/") or get_domain(url)

            self.logger.info("Scraped OK: %s title=%r", url, title)
            return {
                "url": url,
                "title": title,
                "content": text_content,
                "html": html,
            }

        except requests.RequestException as e:
            self.logger.error(f"Failed to scrape {url}: {e}")
            self.failed_urls.add(url)
            return None
        except ImportError as e:
            if self.use_browser:
                self.logger.error(
                    f"Browser fetch requires Playwright. "
                    "Run: pip install playwright && playwright install chromium"
                )
            else:
                self.logger.error(f"Failed to scrape {url}: {e}")
            self.failed_urls.add(url)
            return None
        except Exception as e:
            self.logger.error(f"Failed to scrape {url}: {e}")
            self.failed_urls.add(url)
            return None

    def iter_scraped_pages(
        self,
        start_url: str,
        include_external: bool = False,
        allowed_subdomain: Optional[str] = None,
        path_prefix: Optional[str] = None,
    ) -> Iterator[Dict[str, str]]:
        """
        Crawl a website and yield each successfully scraped page.

        Args:
            start_url: Starting URL to scrape.
            include_external: Whether to include external links.
            allowed_subdomain: Host restriction for crawled URLs.
            path_prefix: Optional path prefix restriction.

        Yields:
            Dictionaries with url, title, content, and html keys.
        """
        raw_subdomain = (allowed_subdomain or "").strip().lower()
        if raw_subdomain and "/" in raw_subdomain:
            parts = raw_subdomain.split("/", 1)
            allowed_netloc = get_domain("https://" + parts[0].strip())
            path_prefix = path_prefix or (
                "/" + parts[1].strip() if parts[1].strip() else None
            )
        else:
            allowed_netloc = (allowed_subdomain or get_domain(start_url)).strip().lower()

        if allowed_subdomain and get_domain(start_url).lower() != allowed_netloc and "/" not in (allowed_subdomain or ""):
            self.logger.warning(
                f"Start URL host ({get_domain(start_url)}) does not match "
                f"--subdomain ({allowed_subdomain}); only pages under {allowed_netloc} will be scraped."
            )

        self.logger.info(f"Starting scrape of: {start_url}")
        self.logger.info(f"Restricting to subdomain: {allowed_netloc}")
        if path_prefix:
            self.logger.info(f"Restricting to path prefix: {path_prefix}")
        self.logger.info(f"Max files: {self.max_files}")

        urls_to_scrape: Set[str] = set()
        if url_matches_netloc(start_url, allowed_netloc) and url_path_under_prefix(
            start_url, path_prefix
        ):
            urls_to_scrape.add(start_url)
        if not urls_to_scrape:
            self.logger.error(
                f"Start URL is not under subdomain {allowed_netloc}"
                + (f" or path prefix {path_prefix!r}" if path_prefix else "")
                + ". Aborting."
            )
            return

        pages_yielded = 0

        while urls_to_scrape and pages_yielded < self.max_files:
            current_url = urls_to_scrape.pop()

            if current_url in self.scraped_urls:
                continue

            queue_size = len(urls_to_scrape)
            self.logger.info(
                "Queue: %d url(s) remaining, processing page %d/%d",
                queue_size,
                pages_yielded + 1,
                self.max_files,
            )
            self.scraped_urls.add(current_url)
            scraped_data = self.scrape_url(current_url)
            if not scraped_data:
                self.logger.warning("Skipping agent for failed fetch: %s", current_url)
                continue

            pages_yielded += 1
            self.scraped_content.append(scraped_data)
            yield scraped_data

            if pages_yielded < self.max_files:
                new_links = get_internal_links(scraped_data["html"], current_url)
                if include_external:
                    new_links.update(
                        self._get_external_links(scraped_data["html"], current_url)
                    )

                added = 0
                for link in new_links:
                    if (
                        url_matches_netloc(link, allowed_netloc)
                        and url_path_under_prefix(link, path_prefix)
                        and link not in self.scraped_urls
                        and link not in self.failed_urls
                    ):
                        urls_to_scrape.add(link)
                        added += 1
                self.logger.info(
                    f"Found {len(new_links)} link(s) on page, {added} new URL(s) to scrape"
                )

            if self.delay > 0:
                time.sleep(self.delay)

    def scrape_website(
        self,
        start_url: str,
        output_dir: str = "./scraped_docs/scraped_data",
        include_external: bool = False,
        allowed_subdomain: Optional[str] = None,
        path_prefix: Optional[str] = None,
        agent: Optional["ContentAgent"] = None,
    ) -> Dict[str, any]:
        """
        Scrape a website starting from the given URL.

        Args:
            start_url: Starting URL to scrape (used for domain/path filtering).
            output_dir: Directory to save scraped content
            include_external: Whether to include external links
            allowed_subdomain: If set, only scrape URLs under this host (e.g. "docs.example.com").
                When not set, only the same host as start_url is scraped.
            path_prefix: If set, only scrape URLs whose path starts with this prefix (e.g. "/docs/en").

        Args:
            agent: Optional ContentAgent. When set, each page is processed by the
                agent instead of being saved directly.

        Returns:
            Dictionary with scraping results and statistics
        """
        output_path = Path(output_dir)
        create_output_directory(output_path)
        self.logger.info(f"Output directory: {output_path.absolute()}")

        files_created = 0
        pages_processed = 0
        saved = 0
        consolidated = 0
        skipped = 0
        errors = 0

        pbar = tqdm(total=self.max_files, unit="page", dynamic_ncols=True)
        try:
            for scraped_data in self.iter_scraped_pages(
                start_url=start_url,
                include_external=include_external,
                allowed_subdomain=allowed_subdomain,
                path_prefix=path_prefix,
            ):
                pages_processed += 1
                if agent is not None:
                    self.logger.info(
                        "Handing off to agent (%d/%d): %s",
                        pages_processed,
                        self.max_files,
                        scraped_data["url"],
                    )
                    result = agent.process_document(scraped_data)
                    self.logger.info(
                        "Agent result for %s: %s (%s)",
                        scraped_data["url"],
                        result.decision.value,
                        result.reason,
                    )
                    decision = result.decision.value
                    if decision == "SAVE":
                        saved += 1
                        files_created += 1
                    elif decision == "CONSOLIDATE":
                        consolidated += 1
                        files_created += 1
                    elif decision == "SKIP":
                        skipped += 1
                    else:
                        errors += 1
                    pbar.set_postfix(
                        saved=saved,
                        consolidated=consolidated,
                        skipped=skipped,
                        errors=errors,
                    )
                else:
                    filename = self._create_filename(
                        scraped_data["title"], files_created
                    )
                    file_path = output_path / f"{filename}.txt"
                    try:
                        with open(file_path, "w", encoding="utf-8") as handle:
                            handle.write(f"URL: {scraped_data['url']}\n")
                            handle.write(f"Title: {scraped_data['title']}\n")
                            handle.write("-" * 50 + "\n\n")
                            handle.write(scraped_data["content"])
                        files_created += 1
                        self.logger.info(f"Saved: {filename}.txt")
                    except OSError as exc:
                        self.logger.error(
                            f"Failed to save file {filename}.txt: {exc}"
                        )
                    pbar.set_postfix(files=files_created)
                pbar.update(1)
        finally:
            pbar.close()

        summary = {
            "files_created": files_created,
            "pages_processed": pages_processed,
            "urls_scraped": len(self.scraped_urls),
            "urls_failed": len(self.failed_urls),
            "output_directory": str(output_path.absolute()),
        }
        if agent is not None:
            summary["agent_stats"] = {
                "saved": agent.stats.saved,
                "consolidated": agent.stats.consolidated,
                "skipped": agent.stats.skipped,
                "errors": agent.stats.errors,
            }

        self.logger.info(f"Scraping completed: {summary}")
        return summary

    def _create_filename(self, title: str, index: int) -> str:
        """
        Create a unique filename from title and index.

        Args:
            title: Page title
            index: File index

        Returns:
            Clean filename
        """
        clean_title = clean_filename(title)
        return f"{index:03d}_{clean_title}"

    def _get_external_links(self, html: str, base_url: str) -> Set[str]:
        """
        Extract external links from HTML content.

        Args:
            html: HTML content
            base_url: Base URL for the page

        Returns:
            Set of external URLs
        """
        soup = BeautifulSoup(html, "html.parser")
        external_links = set()
        base_domain = get_domain(base_url)

        for link in soup.find_all("a", href=True):
            href = link["href"]

            # Skip empty hrefs, fragments, and mailto/tel links
            if not href or href.startswith("#") or href.startswith(("mailto:", "tel:")):
                continue

            # Check if it's an external link
            if href.startswith("http") and get_domain(href) != base_domain:
                external_links.add(href)

        return external_links

    def get_stats(self) -> Dict[str, any]:
        """
        Get scraping statistics.

        Returns:
            Dictionary with scraping statistics
        """
        return {
            "total_urls_attempted": len(self.scraped_urls) + len(self.failed_urls),
            "successful_scrapes": len(self.scraped_urls),
            "failed_scrapes": len(self.failed_urls),
            "success_rate": (
                len(self.scraped_urls) / (len(self.scraped_urls) + len(self.failed_urls))
                if (len(self.scraped_urls) + len(self.failed_urls)) > 0
                else 0
            ),
            "content_files": len(self.scraped_content),
        }
