"""Utility functions for web scraping."""

import re
import urllib.parse
from pathlib import Path
from typing import List, Optional, Set

from bs4 import BeautifulSoup


def clean_filename(text: str, max_length: int = 50) -> str:
    """
    Clean and sanitize text for use as a filename.
    
    Args:
        text: Text to clean
        max_length: Maximum length of filename
        
    Returns:
        Clean filename string
    """
    # Remove HTML tags if present
    text = re.sub(r'<[^>]+>', '', text)
    
    # Replace problematic characters
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    
    # Replace multiple spaces/underscores with single underscore
    text = re.sub(r'[\s_]+', '_', text)
    
    # Remove leading/trailing underscores
    text = text.strip('_')
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length].rstrip('_')
    
    # Ensure we have a filename
    if not text:
        text = "scraped_content"
    
    return text


def extract_text_content(html: str) -> str:
    """
    Extract clean text content from HTML.
    
    Args:
        html: HTML content as string
        
    Returns:
        Clean text content
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.extract()
    
    # Get text and clean it up
    text = soup.get_text()
    
    # Break into lines and remove leading/trailing space
    lines = (line.strip() for line in text.splitlines())
    
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    
    # Drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text


def get_domain(url: str) -> str:
    """
    Extract domain from URL.
    
    Args:
        url: Full URL
        
    Returns:
        Domain name
    """
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc


def is_same_domain(url1: str, url2: str) -> bool:
    """
    Check if two URLs are from the same domain.

    Args:
        url1: First URL
        url2: Second URL

    Returns:
        True if same domain, False otherwise
    """
    return get_domain(url1) == get_domain(url2)


def url_matches_netloc(url: str, allowed_netloc: str) -> bool:
    """
    Check if a URL belongs to the given subdomain/host (netloc).

    Args:
        url: URL to check
        allowed_netloc: Required host (e.g. "docs.example.com")

    Returns:
        True if the URL's netloc equals allowed_netloc, False otherwise
    """
    if not url or not url.startswith(("http://", "https://")):
        return False
    return get_domain(url) == allowed_netloc


def url_path_under_prefix(url: str, path_prefix: Optional[str]) -> bool:
    """
    Check if a URL's path is under the given path prefix.

    Args:
        url: URL to check
        path_prefix: Path prefix (e.g. "/docs/en" or "docs/en"). If None, returns True.

    Returns:
        True if path_prefix is None or the URL path starts with the normalized prefix.
    """
    if not path_prefix or not path_prefix.strip():
        return True
    if not url or not url.startswith(("http://", "https://")):
        return False
    prefix = path_prefix.strip().lower()
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    if not prefix.endswith("/"):
        prefix = prefix + "/"
    parsed = urllib.parse.urlparse(url)
    path = (parsed.path or "/").lower()
    if not path.startswith("/"):
        path = "/" + path
    # Match path that equals prefix or starts with prefix (so /docs/en matches /docs/en and /docs/en/...)
    return path == prefix.rstrip("/") or path.startswith(prefix)


def normalize_url(url: str, base_url: str) -> str:
    """
    Normalize a URL by making it absolute and removing fragments.
    
    Args:
        url: URL to normalize (may be relative)
        base_url: Base URL for resolving relative URLs
        
    Returns:
        Normalized absolute URL
    """
    # Join with base URL to handle relative URLs
    absolute_url = urllib.parse.urljoin(base_url, url)
    
    # Parse and rebuild without fragment
    parsed = urllib.parse.urlparse(absolute_url)
    normalized = urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, 
         parsed.params, parsed.query, '')
    )
    
    return normalized


def extract_links_from_html(
    html: str,
    base_url: str,
    path_prefix: Optional[str] = None,
) -> List[str]:
    """
    Extract all <a href> links from HTML and return as absolute URLs.
    Optionally filter by path prefix. Useful for seeding a scrape from
    JS-rendered HTML (e.g. a saved sidenav snippet).

    Args:
        html: HTML content (e.g. from a saved snippet or page)
        base_url: Base URL for resolving relative hrefs (e.g. "https://cursor.com")
        path_prefix: If set, only return URLs whose path starts with this prefix.

    Returns:
        Sorted list of unique absolute URLs.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: Set[str] = set()
    base_domain = get_domain(base_url)

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href or href.startswith("#") or href.startswith(("mailto:", "tel:")):
            continue
        normalized = normalize_url(href, base_url)
        if get_domain(normalized) != base_domain:
            continue
        if path_prefix and not url_path_under_prefix(normalized, path_prefix):
            continue
        seen.add(normalized)
    return sorted(seen)


def get_internal_links(html: str, base_url: str) -> Set[str]:
    """
    Extract all internal links from HTML content.
    
    Args:
        html: HTML content
        base_url: Base URL for the page
        
    Returns:
        Set of normalized internal URLs
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = set()
    base_domain = get_domain(base_url)
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        # Skip empty hrefs, fragments, and mailto/tel links
        if not href or href.startswith('#') or href.startswith(('mailto:', 'tel:')):
            continue
            
        # Normalize the URL
        normalized_url = normalize_url(href, base_url)
        
        # Only include if it's from the same domain
        if get_domain(normalized_url) == base_domain:
            links.add(normalized_url)
    
    return links


def create_output_directory(output_dir: Path) -> None:
    """
    Create output directory if it doesn't exist.
    
    Args:
        output_dir: Path to output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)
