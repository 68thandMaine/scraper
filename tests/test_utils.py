"""Tests for utility functions."""

import tempfile
from pathlib import Path

import pytest

from web_scraper.utils import (
    clean_filename,
    create_output_directory,
    extract_links_from_html,
    extract_text_content,
    get_domain,
    get_internal_links,
    is_same_domain,
    normalize_url,
    url_matches_netloc,
    url_path_under_prefix,
)


class TestCleanFilename:
    """Tests for clean_filename function."""

    def test_basic_cleaning(self) -> None:
        """Test basic filename cleaning."""
        assert clean_filename("Hello World") == "Hello_World"
        assert clean_filename("test/file*name") == "test_file_name"
        assert clean_filename("file<>name") == "file_name"

    def test_html_tag_removal(self) -> None:
        """Test HTML tag removal."""
        assert clean_filename("<h1>Title</h1>") == "Title"
        assert clean_filename("Text with <em>emphasis</em>") == "Text_with_emphasis"

    def test_length_truncation(self) -> None:
        """Test filename length truncation."""
        long_text = "a" * 100
        result = clean_filename(long_text, max_length=20)
        assert len(result) <= 20
        assert result == "a" * 20

    def test_empty_input(self) -> None:
        """Test empty input handling."""
        assert clean_filename("") == "scraped_content"
        assert clean_filename("   ") == "scraped_content"

    def test_special_characters(self) -> None:
        """Test special character handling."""
        assert clean_filename('file"name') == "file_name"
        assert clean_filename("file|name") == "file_name"
        assert clean_filename("file?name") == "file_name"


class TestExtractTextContent:
    """Tests for extract_text_content function."""

    def test_basic_text_extraction(self) -> None:
        """Test basic HTML text extraction."""
        html = "<html><body><h1>Title</h1><p>Paragraph text</p></body></html>"
        result = extract_text_content(html)
        assert "Title" in result
        assert "Paragraph text" in result

    def test_script_style_removal(self) -> None:
        """Test removal of script and style tags."""
        html = """
        <html>
            <head><style>body { color: red; }</style></head>
            <body>
                <h1>Title</h1>
                <script>console.log('test');</script>
                <p>Content</p>
            </body>
        </html>
        """
        result = extract_text_content(html)
        assert "Title" in result
        assert "Content" in result
        assert "color: red" not in result
        assert "console.log" not in result

    def test_empty_html(self) -> None:
        """Test empty HTML handling."""
        assert extract_text_content("") == ""
        assert extract_text_content("<html></html>") == ""

    def test_whitespace_cleanup(self) -> None:
        """Test whitespace cleanup."""
        html = "<html><body><p>Text   with    spaces</p></body></html>"
        result = extract_text_content(html)
        assert "Text" in result and "with" in result and "spaces" in result


class TestUrlFunctions:
    """Tests for URL-related functions."""

    def test_get_domain(self) -> None:
        """Test domain extraction."""
        assert get_domain("https://example.com/path") == "example.com"
        assert get_domain("http://subdomain.example.com") == "subdomain.example.com"
        assert get_domain("https://example.com:8080") == "example.com:8080"

    def test_is_same_domain(self) -> None:
        """Test domain comparison."""
        assert is_same_domain("https://example.com/page1", "https://example.com/page2")
        assert not is_same_domain("https://example.com", "https://other.com")
        assert not is_same_domain("https://example.com", "https://sub.example.com")

    def test_normalize_url(self) -> None:
        """Test URL normalization."""
        base_url = "https://example.com/section/"
        
        # Test relative URL resolution
        assert normalize_url("page.html", base_url) == "https://example.com/section/page.html"
        assert normalize_url("/about", base_url) == "https://example.com/about"
        
        # Test fragment removal
        assert normalize_url("page.html#section", base_url) == "https://example.com/section/page.html"
        
        # Test absolute URL handling
        assert normalize_url("https://other.com/page", base_url) == "https://other.com/page"

    def test_get_internal_links(self) -> None:
        """Test internal link extraction."""
        html = """
        <html>
            <body>
                <a href="/internal">Internal link</a>
                <a href="https://example.com/page">Same domain</a>
                <a href="https://other.com/page">External link</a>
                <a href="#fragment">Fragment</a>
                <a href="mailto:test@example.com">Email</a>
                <a href="">Empty href</a>
            </body>
        </html>
        """
        
        base_url = "https://example.com/"
        links = get_internal_links(html, base_url)
        
        assert "https://example.com/internal" in links
        assert "https://example.com/page" in links
        assert len([link for link in links if "other.com" in link]) == 0
        assert len([link for link in links if "#" in link]) == 0
        assert len([link for link in links if "mailto:" in link]) == 0

    def test_url_matches_netloc(self) -> None:
        """Test subdomain/netloc matching."""
        assert url_matches_netloc("https://docs.example.com/page", "docs.example.com")
        assert url_matches_netloc("http://docs.example.com", "docs.example.com")
        assert not url_matches_netloc("https://www.example.com/page", "docs.example.com")
        assert not url_matches_netloc("https://example.com", "docs.example.com")
        assert not url_matches_netloc("/relative", "docs.example.com")
        assert not url_matches_netloc("", "docs.example.com")

    def test_url_path_under_prefix(self) -> None:
        """Test path prefix matching."""
        assert url_path_under_prefix("https://example.com/docs/en", "/docs/en")
        assert url_path_under_prefix("https://example.com/docs/en/", "/docs/en")
        assert url_path_under_prefix("https://example.com/docs/en/home", "/docs/en")
        assert url_path_under_prefix("https://example.com/docs/en/home", "docs/en")
        assert not url_path_under_prefix("https://example.com/docs", "/docs/en")
        assert not url_path_under_prefix("https://example.com/other", "/docs/en")
        assert url_path_under_prefix("https://example.com/anything", None)
        assert url_path_under_prefix("https://example.com/anything", "")

    def test_extract_links_from_html(self) -> None:
        """Test link extraction from HTML snippet (e.g. sidenav)."""
        html = """
        <div>
            <a href="/docs">Welcome</a>
            <a href="/docs/get-started/quickstart">Quickstart</a>
            <a href="https://other.com/page">External</a>
            <a href="/docs/agent/overview">Overview</a>
        </div>
        """
        urls = extract_links_from_html(html, "https://cursor.com", path_prefix="/docs")
        assert "https://cursor.com/docs" in urls
        assert "https://cursor.com/docs/get-started/quickstart" in urls
        assert "https://cursor.com/docs/agent/overview" in urls
        assert len([u for u in urls if "other.com" in u]) == 0
        assert urls == sorted(urls)


class TestCreateOutputDirectory:
    """Tests for create_output_directory function."""

    def test_create_new_directory(self) -> None:
        """Test creating a new directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "new_directory"
            create_output_directory(test_path)
            assert test_path.exists()
            assert test_path.is_dir()

    def test_create_nested_directory(self) -> None:
        """Test creating nested directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "level1" / "level2" / "level3"
            create_output_directory(test_path)
            assert test_path.exists()
            assert test_path.is_dir()

    def test_existing_directory(self) -> None:
        """Test with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)
            # Should not raise an error
            create_output_directory(test_path)
            assert test_path.exists()
            assert test_path.is_dir()
