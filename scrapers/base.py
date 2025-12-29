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

        # Skip navigation and reference sections
        if section.find(class_=re.compile(r'nav|reference|toc|citation', re.IGNORECASE)):
            return quotes

        # Look for list items (common format for quotes)
        for li in section.find_all("li"):
            # Skip if it's primarily a link to another page
            links = li.find_all("a", href=re.compile(r'/wiki/'))
            if links and len(li.get_text().strip()) < 50:
                # If it's mostly links and short, likely navigation
                continue
            
            # Skip if it's too short (likely navigation or metadata)
            if len(li.get_text().strip()) < 20:
                continue
            
            # Skip if it's in a reference/citation context
            if li.find_parent(class_=re.compile(r'reference|citation|notes', re.IGNORECASE)):
                continue
            
            text = self.normalize_text(li.get_text())
            if self._is_valid_quote(text):
                quotes.append(text)

        # Also check for paragraph tags, but be more selective
        for p in section.find_all("p"):
            # Skip if it's in a reference section
            if p.find_parent(class_=re.compile(r'reference|citation|notes', re.IGNORECASE)):
                continue
            
            # Skip if it's mostly links
            links = p.find_all("a", href=re.compile(r'/wiki/'))
            if links and len(p.get_text().strip()) < 50:
                continue
            
            text = self.normalize_text(p.get_text())
            if self._is_valid_quote(text):
                quotes.append(text)

        return quotes

    def _is_valid_quote(self, text: str) -> bool:
        """
        Check if text is a valid quote (not a reference or citation).
        
        Strict validation to prevent garbage entries:
        - Minimum 30 characters
        - Must have sentence ending OR be 150+ chars
        - Rejects citations, references, titles, metadata
        
        Args:
            text: Text to validate
            
        Returns:
            True if it's a valid quote
        """
        if not text or len(text) < 30:
            return False
        
        # Remove surrounding quotes if present
        text = text.strip()
        if (text.startswith('"') and text.endswith('"')) or \
           (text.startswith("'") and text.endswith("'")):
            text = text[1:-1].strip()
        
        # Too short after cleaning (strict: 30 chars minimum)
        if len(text) < 30:
            return False
        
        # Check for sentence ending
        has_ending = any(text.rstrip().endswith(p) for p in ['.', '!', '?', '…'])
        
        # NEW: Must have sentence ending OR be very long (150+ chars)
        if not has_ending and len(text) < 150:
            return False
        
        # NEW: Reject Title Case without sentence endings (likely book titles)
        if text.istitle() and not has_ending:
            return False
        
        # Check for citation patterns (references, not quotes)
        import re
        
        # Publication citations: "Title", Publication (Date)
        if re.match(r'^"[^"]+",\s+[A-Z][^,]+(?:,\s*\d{1,2}\s+\w+\s+\d{4})?\)?$', text):
            return False
        
        # References with dates: "Title" (written Date, published Date)[number]
        if re.match(r'^"[^"]+"\s*\([^)]*(?:written|published)[^)]*\)\s*\[\d+\]$', text):
            return False
        
        # Letter citations: "Letter to ... (Date), in ..."
        if re.match(r'^Letter\s+to\s+[^,]+,\s*\([^)]+\),\s*(?:in|as|as quoted in)', text, re.IGNORECASE):
            return False
        
        # Comment citations: "Comment while ... (Date), as quoted in ..."
        if re.match(r'^Comment\s+(?:while|on)[^,]+,\s*\([^)]+\),\s*as quoted in', text, re.IGNORECASE):
            return False
        
        # Publication info: "Title" (Date), in ...
        if re.match(r'^"[^"]+"\s*\([^)]+\),\s*(?:in|as|as cited|as quoted)', text):
            return False
        
        # Just publication info without quotes
        if re.match(r'^[A-Z][^,]+,\s*\([^)]+\),\s*(?:in|as|as cited|as quoted)', text):
            return False
        
        # Chapter references: "Title" (Date), Ch. X or Chapter X (standalone)
        # Only match if it's a short entry ending with chapter reference
        if re.match(r'^[A-Z][^.!?]{0,80},\s*\([^)]+\),\s*Ch\.?\s*\d+\s*$', text):
            return False
        if re.match(r'^[A-Z][^.!?]{0,80},\s*\([^)]+\),\s*Chapter\s+\d+\s*$', text):
            return False
        # Chapter references without dates
        if re.match(r'^[A-Z][^.!?]{0,80},\s*Ch\.?\s*\d+\s*$', text):
            return False
        if re.match(r'^[A-Z][^.!?]{0,80},\s*Chapter\s+\d+\s*$', text):
            return False
        
        # Records starting with ↑ (upward arrow - footnote references)
        if text.startswith('↑') or text.startswith('\u2191'):
            return False
        
        # Records containing "см." anywhere (Russian "see" - reference marker) - ALL of them
        if 'см.' in text or 'См.' in text:
            return False
        
        # Records starting with "Категория:" (Russian "Category:")
        if text.startswith('Категория:') or text.startswith('категория:'):
            return False
        
        # Records with "Famous Quotations" or "Quotations"
        if re.search(r'\bFamous\s+Quotations\b', text, re.IGNORECASE) or \
           re.search(r'\bQuotations\b', text, re.IGNORECASE):
            return False
        
        # Part references (English): Part I, Part 1, Part One, Part A
        if re.match(r'^Part\s+[IVX]+(?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.match(r'^Part\s+\d+(?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.match(r'^Part\s+[A-Z](?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.match(r'^Part\s+(?:One|Two|Three|Four|Five)(?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.search(r',\s+Part\s+[IVX]+\s*$', text, re.IGNORECASE) or \
           re.search(r',\s+Part\s+\d+\s*$', text, re.IGNORECASE):
            return False
        
        # Part references (Russian): Часть I, Часть 1, Часть первая
        if re.match(r'^Часть\s+[IVX]+(?:\s*[:\-]|\s*$)', text) or \
           re.match(r'^Часть\s+\d+(?:\s*[:\-]|\s*$)', text) or \
           re.match(r'^Часть\s+[А-ЯЁ]+(?:\s*[:\-]|\s*$)', text) or \
           re.search(r',\s+Часть\s+[IVX]+\s*$', text) or \
           re.search(r',\s+Часть\s+\d+\s*$', text):
            return False
        
        # Section references (English): Section I, Section 1, Section A
        if re.match(r'^Section\s+[IVX]+(?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.match(r'^Section\s+\d+(?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.match(r'^Section\s+[A-Z](?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.search(r',\s+Section\s+[IVX]+\s*$', text, re.IGNORECASE) or \
           re.search(r',\s+Section\s+\d+\s*$', text, re.IGNORECASE):
            return False
        
        # Section references (Russian): Раздел 1, Секция 1
        if re.match(r'^Раздел\s+\d+(?:\s*[:\-]|\s*$)', text) or \
           re.match(r'^Секция\s+\d+(?:\s*[:\-]|\s*$)', text) or \
           re.search(r',\s+Раздел\s+\d+\s*$', text) or \
           re.search(r',\s+Секция\s+\d+\s*$', text):
            return False
        
        # Article references (English): Article I, Article 1
        if re.match(r'^Article\s+[IVX]+(?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.match(r'^Article\s+\d+(?:\s*[:\-]|\s*$)', text, re.IGNORECASE) or \
           re.search(r',\s+Article\s+[IVX]+\s*$', text, re.IGNORECASE) or \
           re.search(r',\s+Article\s+\d+\s*$', text, re.IGNORECASE):
            return False
        
        # Article references (Russian): Статья 1
        if re.match(r'^Статья\s+\d+(?:\s*[:\-]|\s*$)', text) or \
           re.search(r',\s+Статья\s+\d+\s*$', text):
            return False
        
        # Book/article title patterns (standalone titles without quotes, no sentence ending)
        # Pattern: Title (Year) - no sentence ending
        if re.match(r'^[A-ZА-ЯЁ][^.!?]{10,150}\s*\([^)]*\d{4}[^)]*\)\s*$', text):
            return False
        # Pattern: Title, Subtitle - no sentence ending
        if re.match(r'^[A-ZА-ЯЁ][^.!?]{10,150},\s*[A-ZА-ЯЁ][^.!?]{5,50}\s*$', text):
            return False
        # Pattern: Title: Subtitle - no sentence ending
        if re.match(r'^[A-ZА-ЯЁ][^.!?]{10,150}:\s*[A-ZА-ЯЁ][^.!?]{5,50}\s*$', text):
            return False
        
        # STRICT: Reject ANY scene references (Act, Scene, Scenes, Сцена)
        if re.search(r'\bAct\s+[IVX]+,\s+scene\s+[ivx]+\b', text, re.IGNORECASE) or \
           re.search(r'\bAct\s+\d+,\s+Scene\s+\d+\b', text, re.IGNORECASE) or \
           re.search(r'\bAct\s+[IVX]+\b', text, re.IGNORECASE) or \
           re.search(r'\bScene\s+\d+\b', text, re.IGNORECASE) or \
           re.search(r'\bScenes\s+\d+\b', text, re.IGNORECASE) or \
           re.search(r'\bСцена\s+\d+\b', text) or \
           re.match(r'^Scenes?,', text, re.IGNORECASE) or \
           re.match(r'^Scene\s*,', text, re.IGNORECASE):
            return False
        
        # STRICT: Reject ANY chapter references (Ch., Chapter, Гл., Глава)
        if re.search(r'\bCh\.\s*\d+', text, re.IGNORECASE) or \
           re.search(r'\bCh\s+\d+', text, re.IGNORECASE) or \
           re.search(r'\bChapter\s+\d+', text, re.IGNORECASE) or \
           re.search(r'\bГл\.\s*\d+', text) or \
           re.search(r'\bГлава\s+\d+', text):
            return False
        
        # "published as/by" patterns
        if re.search(r'\bpublished\s+as\b', text, re.IGNORECASE) or \
           re.search(r'\bpublished\s+by\b', text, re.IGNORECASE):
            return False
        
        # HTTP/HTTPS links (URLs)
        if re.search(r'https?://', text) or re.search(r'www\.', text):
            return False
        
        # STRICT: Reject ANY volume references (Vol., Volume, Том)
        if re.search(r'\bVol(?:ume)?\.?\s*\d+\b', text, re.IGNORECASE) or \
           re.search(r'\bТом\.?\s*\d+\b', text) or \
           re.search(r'\bVol\.', text, re.IGNORECASE):
            return False
        
        # STRICT: Reject author patterns (likely citations)
        if re.search(r'\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text, re.IGNORECASE) or \
           re.search(r'\bавтор[а-яё]*:\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)+\b', text):
            # Reject if it looks like a citation with author
            return False
        
        # STRICT: Reject ANY publishing house names (anywhere, any length)
        publishing_patterns = [
            r'\b(?:Published\s+by|Publisher):?\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Press|Publishing|House))?\b',
            r'\b(?:Penguin|Random House|HarperCollins|Simon & Schuster|Macmillan|Hachette|Scholastic|Oxford University Press|Cambridge University Press|Harvard University Press|MIT Press|Princeton University Press|Yale University Press|University Press|Press,|Publishers?|Publishing|Editions?|Books?)\b',
            r'\b(?:Издательство|Издатель):?\s*[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b',
        ]
        for pattern in publishing_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Reject ANY publishing house reference - user wants no garbage
                return False
        
        # STRICT: Reject ANY dates in parentheses (anywhere in text, not just at end)
        # English month names (full and abbreviated)
        english_months = [
            r'January', r'February', r'March', r'April', r'May', r'June',
            r'July', r'August', r'September', r'October', r'November', r'December',
            r'Jan', r'Feb', r'Mar', r'Apr', r'Jun', r'Jul', r'Aug',
            r'Sep', r'Sept', r'Oct', r'Nov', r'Dec'
        ]
        # Russian month names (full and abbreviated)
        russian_months = [
            r'января', r'февраля', r'марта', r'апреля', r'мая', r'июня',
            r'июля', r'августа', r'сентября', r'октября', r'ноября', r'декабря',
            r'янв', r'фев', r'мар', r'апр', r'май', r'июн', r'июл',
            r'авг', r'сен', r'окт', r'ноя', r'дек'
        ]
        
        # Pattern: (Date) anywhere - be very strict
        # English dates: (May 7, 2007), (May 7 2007), (7 May 2007), (May 2007)
        if re.search(r'\([^)]*(?:' + '|'.join(english_months) + r')[^)]*\d{4}[^)]*\)', text, re.IGNORECASE) or \
           re.search(r'\(\d{1,2}\s+(?:' + '|'.join(english_months) + r')\s+\d{4}\)', text, re.IGNORECASE) or \
           re.search(r'\(\d{1,2}\s+\w+\s+\d{4}\)', text) or \
           re.search(r'\(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\)', text) or \
           re.search(r'\([^)]*(?:' + '|'.join(russian_months) + r')[^)]*\d{4}[^)]*\)', text, re.IGNORECASE) or \
           re.search(r'\(\d{4}\)', text):
            # Reject if date appears anywhere - user wants no dates
            return False
        
        # STRICT: Reject author year ranges: (1828—1910), (1828-1910), (1828–1910)
        # These are author birth/death years, not quotes
        if re.search(r'\(\d{4}[\s]*[—–-][\s]*\d{4}\)', text):
            return False
        
        # STRICT: Reject if it contains place names (common patterns)
        # Look for patterns like "in London", "in Paris", "at Oxford", etc.
        place_patterns = [
            r'\bin\s+[A-Z][a-z]+\s+(?:University|College|Press|House|Theatre|Theater)',
            r'\bat\s+[A-Z][a-z]+\s+(?:University|College|Press|House)',
            r',\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:University|College|Press|House)',
        ]
        for pattern in place_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        # Check for positive quote indicators
        if self._has_quote_indicators(text):
            return True
        
        # Already checked above: must have sentence ending OR be 150+ chars
        # This is just a final safety check
        if not has_ending and len(text) < 150:
            return False
        
        return True
    
    def _has_quote_indicators(self, text: str) -> bool:
        """
        Check if text has indicators of being a quote.
        
        Args:
            text: Text to check
            
        Returns:
            True if it has quote indicators
        """
        # Has quotation marks (not just at start/end)
        if '"' in text[1:-1] if len(text) > 2 else False:
            return True
        if "'" in text[1:-1] if len(text) > 2 else False:
            return True
        
        # Has attribution pattern (— Author, – Author, - Author)
        if re.search(r'[—–-]\s*[A-ZА-ЯЁ][a-zа-яё]+(?:\s+[A-ZА-ЯЁ][a-zа-яё]+)+', text):
            return True
        
        # Has quote verbs
        quote_verbs = [
            r'\bsaid\b', r'\bwrote\b', r'\bquoted\b', r'\bremarked\b',
            r'\bdeclared\b', r'\bstated\b', r'\bnoted\b', r'\bobserved\b',
            r'\bsaid\b', r'\bсказал\b', r'\bписал\b', r'\bотметил\b',
            r'\bзаявил\b', r'\bподчеркнул\b'
        ]
        for verb_pattern in quote_verbs:
            if re.search(verb_pattern, text, re.IGNORECASE):
                return True
        
        # Is a complete sentence (has sentence ending)
        if re.search(r'[.!?]\s*$', text):
            return True
        
        return False

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

