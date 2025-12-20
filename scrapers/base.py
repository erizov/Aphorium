"""
Base scraper class with common functionality.
"""

import time
import re
from typing import List, Optional
from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup

from config import settings
from logger_config import logger


class BaseScraper(ABC):
    """Base class for WikiQuote scrapers."""

    def __init__(self, base_url: str, delay: float = 1.0):
        """
        Initialize scraper.

        Args:
            base_url: Base URL for WikiQuote site
            delay: Delay between requests in seconds
        """
        self.base_url = base_url
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Aphorium/1.0 (Educational Project)"
        })

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a web page.

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup object or None if failed
        """
        try:
            time.sleep(self.delay)  # Rate limiting
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, "lxml")
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

    def normalize_text(self, text: str) -> str:
        """
        Normalize quote text.

        Args:
            text: Raw text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove leading/trailing whitespace
        text = text.strip()
        # Remove quotes if entire text is quoted
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        if text.startswith("'") and text.endswith("'"):
            text = text[1:-1].strip()

        return text

    def extract_quotes_from_section(
        self,
        section: BeautifulSoup
    ) -> List[str]:
        """
        Extract quotes from a section element.

        Args:
            section: BeautifulSoup section element

        Returns:
            List of quote texts
        """
        quotes = []
        if not section:
            return quotes

        # Look for list items (common format for quotes)
        for li in section.find_all("li"):
            text = self.normalize_text(li.get_text())
            if text and len(text) > 10:  # Minimum quote length
                quotes.append(text)

        # Also check for paragraph tags
        for p in section.find_all("p"):
            text = self.normalize_text(p.get_text())
            if text and len(text) > 10:
                # Check if it looks like a quote (not just description)
                if not text.lower().startswith(("this", "the", "a ", "an ")):
                    quotes.append(text)

        return quotes

    @abstractmethod
    def scrape_author_page(self, author_name: str) -> dict:
        """
        Scrape an author's WikiQuote page.

        Args:
            author_name: Author name

        Returns:
            Dictionary with author info and quotes
        """
        pass

    @abstractmethod
    def get_author_url(self, author_name: str) -> str:
        """
        Get WikiQuote URL for an author.

        Args:
            author_name: Author name

        Returns:
            Full URL
        """
        pass

