"""Web Scraper v2 - A comprehensive web scraping tool."""

__version__ = "2.0.0"
__author__ = "Chris Rudnicky"

from .scraper import WebScraper
from .utils import clean_filename, extract_text_content

__all__ = ["WebScraper", "clean_filename", "extract_text_content"]
