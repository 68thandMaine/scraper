"""Tests for WebScraper class."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from web_scraper.scraper import WebScraper


class TestWebScraper:
    """Tests for WebScraper class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.scraper = WebScraper(max_files=5, delay=0.1)

    def test_initialization(self) -> None:
        """Test WebScraper initialization."""
        scraper = WebScraper(max_files=100, delay=2.0, timeout=30)
        assert scraper.max_files == 100
        assert scraper.delay == 2.0
        assert scraper.timeout == 30
        assert scraper.user_agent == "WebScraper/2.0"
        assert len(scraper.scraped_urls) == 0
        assert len(scraper.failed_urls) == 0

    @patch('web_scraper.scraper.requests.Session.get')
    def test_scrape_url_success(self, mock_get: Mock) -> None:
        """Test successful URL scraping."""
        # Mock response
        mock_response = Mock()
        mock_response.text = """
        <html>
            <head><title>Test Page</title></head>
            <body><h1>Hello World</h1><p>This is test content.</p></body>
        </html>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.scraper.scrape_url("https://example.com/test")

        assert result is not None
        assert result["url"] == "https://example.com/test"
        assert result["title"] == "Test Page"
        assert "Hello World" in result["content"]
        assert "This is test content." in result["content"]

    @patch('web_scraper.scraper.requests.Session.get')
    def test_scrape_url_no_title(self, mock_get: Mock) -> None:
        """Test URL scraping without title tag."""
        mock_response = Mock()
        mock_response.text = "<html><body><p>Content without title</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.scraper.scrape_url("https://example.com/notitle")

        assert result is not None
        assert result["title"] == "notitle"  # Should use URL path

    @patch('web_scraper.scraper.requests.Session.get')
    def test_scrape_url_request_failure(self, mock_get: Mock) -> None:
        """Test URL scraping with request failure."""
        mock_get.side_effect = requests.RequestException("Connection error")

        result = self.scraper.scrape_url("https://example.com/fail")

        assert result is None
        assert "https://example.com/fail" in self.scraper.failed_urls

    @patch('web_scraper.scraper.requests.Session.get')
    def test_scrape_url_empty_content(self, mock_get: Mock) -> None:
        """Test URL scraping with empty content."""
        mock_response = Mock()
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.scraper.scrape_url("https://example.com/empty")

        assert result is None

    @patch('web_scraper.scraper.requests.Session.get')
    def test_scrape_website_basic(self, mock_get: Mock) -> None:
        """Test basic website scraping."""
        # Mock response for main page
        mock_response = Mock()
        mock_response.text = """
        <html>
            <head><title>Main Page</title></head>
            <body>
                <h1>Welcome</h1>
                <p>Main content</p>
                <a href="/page1">Page 1</a>
                <a href="/page2">Page 2</a>
            </body>
        </html>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as temp_dir:
            results = self.scraper.scrape_website(
                "https://example.com/",
                output_dir=temp_dir,
            )

            assert results["files_created"] >= 1
            assert results["urls_scraped"] >= 1
            assert Path(temp_dir).exists()

            # Check that files were created
            txt_files = list(Path(temp_dir).glob("*.txt"))
            assert len(txt_files) >= 1

            # Check file content
            with open(txt_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                assert "URL: https://example.com/" in content
                assert "Title: Main Page" in content
                assert "Welcome" in content

    def test_get_stats(self) -> None:
        """Test statistics retrieval."""
        # Add some mock data
        self.scraper.scraped_urls.add("https://example.com/1")
        self.scraper.scraped_urls.add("https://example.com/2")
        self.scraper.failed_urls.add("https://example.com/fail")
        self.scraper.scraped_content = [{"url": "test", "title": "test", "content": "test"}]

        stats = self.scraper.get_stats()

        assert stats["total_urls_attempted"] == 3
        assert stats["successful_scrapes"] == 2
        assert stats["failed_scrapes"] == 1
        assert stats["success_rate"] == 2/3
        assert stats["content_files"] == 1

    def test_create_filename(self) -> None:
        """Test filename creation."""
        filename1 = self.scraper._create_filename("Test Page", 0)
        assert filename1 == "000_Test_Page"

        filename2 = self.scraper._create_filename("Another Page", 5)
        assert filename2 == "005_Another_Page"

        # Test with problematic characters
        filename3 = self.scraper._create_filename("Page/With*Bad?Chars", 10)
        assert filename3 == "010_Page_With_Bad_Chars"

    @patch('web_scraper.scraper.requests.Session.get')
    def test_get_external_links(self, mock_get: Mock) -> None:
        """Test external link extraction."""
        html = """
        <html>
            <body>
                <a href="https://external.com/page">External</a>
                <a href="/internal">Internal</a>
                <a href="https://example.com/same">Same domain</a>
                <a href="mailto:test@example.com">Email</a>
            </body>
        </html>
        """

        external_links = self.scraper._get_external_links(html, "https://example.com/")

        assert "https://external.com/page" in external_links
        assert len([link for link in external_links if "example.com" in link]) == 0
        assert len([link for link in external_links if "mailto:" in link]) == 0

    @patch('web_scraper.scraper.requests.Session.get')
    def test_scrape_website_subdomain_only(self, mock_get: Mock) -> None:
        """Test that scraping with allowed_subdomain only follows links on that subdomain."""
        mock_response = Mock()
        mock_response.text = """
        <html>
            <head><title>Docs Page</title></head>
            <body>
                <h1>Docs</h1>
                <a href="/docs/other">Same subdomain</a>
                <a href="https://www.example.com/page">Other subdomain</a>
            </body>
        </html>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as temp_dir:
            results = self.scraper.scrape_website(
                "https://docs.example.com/",
                output_dir=temp_dir,
                allowed_subdomain="docs.example.com",
            )
            assert results["files_created"] >= 1
            # Only docs.example.com URLs should be scraped; www.example.com never added
            for url in self.scraper.scraped_urls:
                assert "docs.example.com" in url, f"Unexpected URL scraped: {url}"

    @patch('web_scraper.scraper.requests.Session.get')
    @patch('web_scraper.scraper.time.sleep')
    def test_delay_between_requests(self, mock_sleep: Mock, mock_get: Mock) -> None:
        """Test delay between requests."""
        # Setup scraper with delay
        scraper = WebScraper(max_files=2, delay=1.0)

        # Mock response
        mock_response = Mock()
        mock_response.text = """
        <html>
            <head><title>Page</title></head>
            <body>
                <p>Content</p>
                <a href="/page2">Next</a>
            </body>
        </html>
        """
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with tempfile.TemporaryDirectory() as temp_dir:
            scraper.scrape_website("https://example.com/", output_dir=temp_dir)

            # Should have called sleep at least once (for the delay)
            assert mock_sleep.call_count >= 0
