"""
English WikiQuote scraper.
"""

import re
from typing import List, Optional
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper
from config import settings
from logger_config import logger


class WikiQuoteEnScraper(BaseScraper):
    """Scraper for English WikiQuote."""

    def __init__(self):
        """Initialize English WikiQuote scraper."""
        super().__init__(
            base_url=settings.wikiquote_en_base_url,
            delay=settings.scrape_delay
        )

    def get_author_url(self, author_name: str) -> str:
        """
        Get WikiQuote URL for an author.

        Args:
            author_name: Author name

        Returns:
            Full URL
        """
        # Replace spaces with underscores for URL
        url_name = author_name.replace(" ", "_")
        return f"{self.base_url}/wiki/{url_name}"

    def scrape_author_page(self, author_name: str) -> dict:
        """
        Scrape an author's WikiQuote page.

        Args:
            author_name: Author name

        Returns:
            Dictionary with author info, bio, and quotes by source
        """
        url = self.get_author_url(author_name)
        soup = self.fetch_page(url)

        if not soup:
            logger.warning(f"Could not fetch page for {author_name}")
            return {
                "author_name": author_name,
                "bio": None,
                "quotes": [],
                "sources": {}
            }

        result = {
            "author_name": author_name,
            "bio": self._extract_bio(soup),
            "quotes": [],
            "sources": {}
        }

        # Extract quotes by source
        # WikiQuote EN typically has sections for different works
        headings = soup.find_all(["h2", "h3"])

        for heading in headings:
            # Skip non-content headings
            if heading.get("id") in ["mw-toc-heading", "References"]:
                continue

            source_title = self.normalize_text(heading.get_text())
            if not source_title:
                continue
            
            # Validate that section heading is a valid work title
            if not self._is_valid_source_title(source_title):
                continue

            # Get quotes from this section
            section = self._get_section_content(heading)
            quotes = self.extract_quotes_from_section(section)

            if quotes:
                result["sources"][source_title] = quotes
                result["quotes"].extend(quotes)

        # If no structured sections, try to get all quotes
        if not result["quotes"]:
            result["quotes"] = self._extract_all_quotes(soup)

        logger.info(
            f"Scraped {len(result['quotes'])} quotes for {author_name}"
        )
        return result

    def _extract_bio(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract author biography.

        Args:
            soup: BeautifulSoup object

        Returns:
            Bio text or None
        """
        # Look for first paragraph after infobox
        content = soup.find("div", class_="mw-parser-output")
        if content:
            first_p = content.find("p")
            if first_p:
                return self.normalize_text(first_p.get_text())
        return None

    def _get_section_content(self, heading) -> Optional[BeautifulSoup]:
        """
        Get content of a section starting from a heading.

        Args:
            heading: Heading element

        Returns:
            Section content or None
        """
        section = []
        current = heading.next_sibling

        while current:
            if current.name in ["h2", "h3"]:
                break
            if current.name:
                section.append(current)
            current = current.next_sibling

        if section:
            # Create a new soup with section elements
            from bs4 import BeautifulSoup as BS
            return BS("".join(str(elem) for elem in section), "lxml")
        return None

    def _extract_all_quotes(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract all quotes when no structured sections found.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of quote texts
        """
        quotes = []
        content = soup.find("div", class_="mw-parser-output")

        if content:
            # Get all list items, but filter more carefully
            for li in content.find_all("li"):
                # Skip if it's primarily a link
                links = li.find_all("a", href=re.compile(r'/wiki/'))
                if links and len(li.get_text().strip()) < 50:
                    continue
                
                # Skip if in reference section
                if li.find_parent(class_=re.compile(r'reference|citation|notes', re.IGNORECASE)):
                    continue
                
                text = self.normalize_text(li.get_text())
                if text and self._is_valid_quote(text):
                    quotes.append(text)

        return quotes
    
    def _is_valid_source_title(self, title: str) -> bool:
        """
        Check if section heading is a valid work title.
        
        Args:
            title: Section heading text
            
        Returns:
            True if it's a valid work title
        """
        # Skip navigation sections
        nav_keywords = [
            "contents", "navigation", "references", "external links",
            "see also", "notes", "sources", "bibliography"
        ]
        if title.lower() in nav_keywords:
            return False
        
        # Skip if it's a reference marker
        if title.startswith("↑") or title.startswith("см."):
            return False
        
        # Should be reasonably long (not just "Part I" or "Chapter 1")
        if len(title) < 5:
            return False
        
        # Skip if it matches reference patterns
        import re
        if re.match(r'^Part\s+[IVX]+(?:\s*[:\-]|\s*$)', title, re.IGNORECASE):
            return False
        if re.match(r'^Chapter\s+\d+(?:\s*[:\-]|\s*$)', title, re.IGNORECASE):
            return False
        if re.match(r'^Section\s+\d+(?:\s*[:\-]|\s*$)', title, re.IGNORECASE):
            return False
        
        return True

