"""
Discover authors from WikiQuote and link orphaned quotes.

This script:
1. Scrapes WikiQuote author index/category pages to get comprehensive author list
2. Creates authors in database with both EN and RU name versions
3. For orphaned quotes, uses reverse lookup to find which author they belong to
4. Links orphaned quotes to discovered authors

Usage:
    python scripts/discover_authors_from_wikiquote.py [--dry-run] [--limit-authors N] [--limit-quotes N]
"""

import sys
import argparse
import time
import re
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote, Author
from scrapers.wikiquote_en import WikiQuoteEnScraper
from scrapers.wikiquote_ru import WikiQuoteRuScraper
from repositories.author_repository import AuthorRepository
from repositories.quote_repository import QuoteRepository
from translit_service import TranslationService
from config import settings
from logger_config import logger


def is_ultra_strict_valid_quote(text: str) -> bool:
    """
    Ultra-strict quote validation.
    
    Rejects quotes that contain:
    - Any numbers (Arabic or Roman)
    - Any names (proper nouns)
    - Places, cities, countries
    - Dates (any format)
    - References to plays, theaters
    - If any doubt, reject
    
    Args:
        text: Quote text to validate
        
    Returns:
        True if quote passes all strict criteria
    """
    if not text or len(text.strip()) < 30:
        return False
    
    text = text.strip()
    
    # Remove surrounding quotes
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    
    if len(text) < 30:
        return False
    
    # Must have sentence ending
    has_ending = any(text.rstrip().endswith(p) for p in ['.', '!', '?', '…'])
    if not has_ending and len(text) < 150:
        return False
    
    # Reject if contains ANY Arabic numbers (0-9)
    if re.search(r'\d', text):
        return False
    
    # Reject if contains Roman numerals (I, II, III, IV, V, VI, VII, VIII, IX, X, etc.)
    # Common patterns: standalone, in parentheses, after words
    roman_patterns = [
        r'\b[IVX]+(?:\s*[IVX]+)*\b',  # Basic Roman numerals
        r'\b[IVXLCDM]+(?:\s*[IVXLCDM]+)*\b',  # Extended Roman numerals
        r'\([IVX]+\)',  # Roman in parentheses
        r'[IVX]+[,\s]',  # Roman followed by comma/space
    ]
    for pattern in roman_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    # Reject if contains proper nouns (names) - very strict
    # Look for capitalized words that aren't at sentence start
    words = text.split()
    if len(words) > 1:
        # Check for name patterns: "Name said", "Name's", "Name,", etc.
        for i in range(1, len(words)):
            word = words[i].strip('.,!?;:()[]{}"\'')
            # If word is capitalized and looks like a name
            if word and word[0].isupper() and len(word) > 2:
                # Check if followed by name indicators
                if i < len(words) - 1:
                    next_word = words[i + 1].strip('.,!?;:()[]{}"\'').lower()
                    name_indicators = [
                        'said', 'says', 'wrote', 'writes', 'told', 'tells', 'asked',
                        'answered', 'replied', 'declared', 'stated', 'noted',
                        'сказал', 'сказала', 'писал', 'писала', 'говорил', 'говорила',
                        'написал', 'написала', 'спросил', 'ответил', 'заявил'
                    ]
                    if next_word in name_indicators:
                        return False
                # Check for possessive
                if word.endswith("'s") or word.endswith("'s"):
                    return False
                # Check if word is followed by comma (common in "Name, ..." patterns)
                if i < len(words) - 1 and words[i + 1].startswith(','):
                    # Might be a name, reject to be safe
                    return False
    
    # Reject if contains place names (cities, countries, places)
    # Common patterns: "in [Place]", "at [Place]", "from [Place]"
    place_patterns = [
        r'\bin\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # "in London", "in New York"
        r'\bat\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # "at Oxford"
        r'\bfrom\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # "from Paris"
        r'\bto\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # "to Berlin"
        # Common city/country names
        r'\b(?:London|Paris|Berlin|Rome|Madrid|Moscow|Tokyo|Beijing|New York|Los Angeles|'
        r'Chicago|Boston|Philadelphia|San Francisco|Washington|Miami|Seattle|Denver|'
        r'Лондон|Париж|Берлин|Рим|Мадрид|Москва|Токио|Пекин|Нью-Йорк)\b',
        r'\b(?:England|France|Germany|Italy|Spain|Russia|Japan|China|USA|United States|'
        r'Англия|Франция|Германия|Италия|Испания|Россия|Япония|США|Соединённые Штаты)\b',
    ]
    for pattern in place_patterns:
        if re.search(pattern, text):
            return False
    
    # Reject if contains dates (any format)
    # Already covered in base validation, but be extra strict
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # MM/DD/YYYY, DD-MM-YY
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',  # YYYY-MM-DD
        r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|'
        r'October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
        r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|'
        r'октября|ноября|декабря|янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)',
        r'\([^)]*\d{4}[^)]*\)',  # Anything with 4-digit year in parentheses
        r'\d{4}',  # Any 4-digit number (likely a year)
    ]
    for pattern in date_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    # Reject if contains references to plays, theaters
    play_theater_patterns = [
        r'\b(?:play|theater|theatre|drama|comedy|tragedy|act|scene|stage|'
        r'пьеса|театр|драма|комедия|трагедия|акт|сцена|сценарий)\b',
        r'\b(?:Broadway|West End|Globe|Shakespeare|Shakespearean)\b',
        r'\b(?:Бродвей|Глобус|Шекспир|шекспировский)\b',
    ]
    for pattern in play_theater_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    # Use base validation logic (replicate key checks from BaseScraper._is_valid_quote)
    # Minimum 30 characters (already checked)
    # Must have sentence ending OR be 150+ chars (already checked)
    
    # Reject Title Case without sentence endings (likely book titles)
    if text.istitle() and not has_ending:
        return False
    
    # Reject citation patterns
    if re.search(r'\b(?:published|written|as quoted|as cited)', text, re.IGNORECASE):
        return False
    
    # Reject if contains "см." (Russian reference marker)
    if 'см.' in text or 'См.' in text:
        return False
    
    # Reject if contains URLs
    if re.search(r'https?://', text) or re.search(r'www\.', text):
        return False
    
    # Reject publishing house references
    if re.search(r'\b(?:Press|Publishing|House|Издательство|Издатель)\b', text, re.IGNORECASE):
        return False
    
    # If we got here and still have doubt, reject
    # Additional checks for common problematic patterns
    
    # Reject if contains too many capitalized words (likely names/places)
    capitalized_words = [w for w in words if w and w[0].isupper()]
    if len(capitalized_words) > 3:  # More than 3 capitalized words is suspicious
        return False
    
    # Reject if contains common name patterns
    if re.search(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', text):  # "John Smith" pattern
        # But allow if it's at the very start (might be quote attribution)
        if not text.startswith('"') and not text.startswith("'"):
            # Check if it's not at the beginning
            match = re.search(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', text)
            if match and match.start() > 10:  # Not at the very start
                return False
    
    return True


def load_quotes_for_author(
    author: Author,
    scraper,
    db,
    language: str,
    max_quotes: int = 5
) -> Dict[str, int]:
    """
    Load up to max_quotes quotes for an author with ultra-strict validation.
    
    Args:
        author: Author to load quotes for
        scraper: WikiQuote scraper instance
        db: Database session
        language: Language code
        max_quotes: Maximum number of quotes to load
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "quotes_loaded": 0,
        "quotes_rejected": 0
    }
    
    try:
        # Get author name for this language
        author_name = None
        if language == "en" and author.name_en:
            author_name = author.name_en
        elif language == "ru" and author.name_ru:
            author_name = author.name_ru
        
        if not author_name:
            return stats
        
        # Scrape author page
        data = scraper.scrape_author_page(author_name)
        
        if not data.get("quotes"):
            return stats
        
        # Collect all quotes
        all_quotes = list(data.get("quotes", []))
        for quotes_list in data.get("sources", {}).values():
            all_quotes.extend(quotes_list)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_quotes = []
        for quote in all_quotes:
            if quote not in seen:
                seen.add(quote)
                unique_quotes.append(quote)
        
        quote_repo = QuoteRepository(db)
        quotes_loaded = 0
        
        # Process quotes with ultra-strict validation
        for quote_text in unique_quotes:
            if quotes_loaded >= max_quotes:
                break
            
            # Apply ultra-strict validation
            if not is_ultra_strict_valid_quote(quote_text):
                stats["quotes_rejected"] += 1
                logger.debug(
                    f"Rejected quote for author {author.id}: "
                    f"{quote_text[:50]}..."
                )
                continue
            
            # Check if quote already exists
            existing = (
                db.query(Quote)
                .filter(
                    Quote.text == quote_text,
                    Quote.language == language
                )
                .first()
            )
            
            if existing:
                # Quote already exists, skip
                continue
            
            # Create new quote
            try:
                quote_repo.create(
                    text=quote_text,
                    author_id=author.id,
                    source_id=None,  # Don't set source for now
                    language=language
                )
                quotes_loaded += 1
                stats["quotes_loaded"] += 1
                logger.debug(
                    f"Loaded quote {quotes_loaded}/{max_quotes} for author "
                    f"{author.id} ({author_name})"
                )
            except Exception as e:
                logger.warning(f"Failed to create quote: {e}")
                stats["quotes_rejected"] += 1
                continue
        
        return stats
        
    except Exception as e:
        logger.error(f"Error loading quotes for author {author.id}: {e}")
        return stats


def scrape_author_index_page(
    scraper,
    category_url: str,
    max_pages: int = 10
) -> Set[str]:
    """
    Scrape author names from WikiQuote category/index pages.
    
    Args:
        scraper: WikiQuote scraper instance
        category_url: URL to category/index page
        max_pages: Maximum number of pages to scrape
        
    Returns:
        Set of author names found
    """
    authors = set()
    
    try:
        soup = scraper.fetch_page(category_url)
        if not soup:
            return authors
        
        # Find all links to author pages
        # WikiQuote category pages typically have links in <li> tags
        # or in <div class="mw-category-group"> sections
        
        # Method 1: Look for links in category groups
        category_groups = soup.find_all("div", class_="mw-category-group")
        for group in category_groups:
            links = group.find_all("a", href=re.compile(r"/wiki/[^:]+$"))
            for link in links:
                author_name = link.get_text().strip()
                if author_name and not author_name.startswith("Category:"):
                    authors.add(author_name)
        
        # Method 2: Look for links in list items
        list_items = soup.find_all("li")
        for li in list_items:
            link = li.find("a", href=re.compile(r"/wiki/[^:]+$"))
            if link:
                author_name = link.get_text().strip()
                if author_name and not author_name.startswith("Category:"):
                    authors.add(author_name)
        
        # Method 3: Look for "next page" link and continue
        next_link = soup.find("a", string=re.compile(r"next.*page", re.I))
        if next_link and max_pages > 1:
            next_url = next_link.get("href")
            if next_url:
                if not next_url.startswith("http"):
                    next_url = scraper.base_url + next_url
                # Recursively scrape next page
                time.sleep(settings.scrape_delay)
                authors.update(
                    scrape_author_index_page(scraper, next_url, max_pages - 1)
                )
        
        logger.debug(f"Found {len(authors)} authors from {category_url}")
        return authors
        
    except Exception as e:
        logger.error(f"Error scraping author index {category_url}: {e}")
        return authors


def get_wikiquote_author_categories() -> Dict[str, List[str]]:
    """
    Get WikiQuote category URLs for author lists.
    
    Returns:
        Dictionary mapping language to list of category URLs
    """
    return {
        "en": [
            "https://en.wikiquote.org/wiki/Category:Authors",
            "https://en.wikiquote.org/wiki/Category:American_authors",
            "https://en.wikiquote.org/wiki/Category:British_authors",
            "https://en.wikiquote.org/wiki/Category:Russian_authors",
            "https://en.wikiquote.org/wiki/Category:French_authors",
            "https://en.wikiquote.org/wiki/Category:German_authors",
            "https://en.wikiquote.org/wiki/Category:Poets",
            "https://en.wikiquote.org/wiki/Category:Philosophers",
        ],
        "ru": [
            "https://ru.wikiquote.org/wiki/Категория:Авторы",
            "https://ru.wikiquote.org/wiki/Категория:Русские_писатели",
            "https://ru.wikiquote.org/wiki/Категория:Поэты",
            "https://ru.wikiquote.org/wiki/Категория:Философы",
        ]
    }


def discover_authors_from_index(
    db,
    language: str,
    dry_run: bool = False,
    limit: Optional[int] = None
) -> Dict[str, int]:
    """
    Discover authors by scraping WikiQuote index pages.
    
    Args:
        db: Database session
        language: Language to scrape ('en' or 'ru')
        dry_run: If True, only report what would be done
        limit: Limit number of authors to process
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "authors_found": 0,
        "authors_created": 0,
        "authors_existing": 0,
        "quotes_loaded": 0,
        "quotes_rejected": 0,
        "errors": 0
    }
    
    try:
        # Initialize scraper
        if language == "en":
            scraper = WikiQuoteEnScraper()
        elif language == "ru":
            scraper = WikiQuoteRuScraper()
        else:
            logger.error(f"Unsupported language: {language}")
            return stats
        
        author_repo = AuthorRepository(db)
        translator = TranslationService(provider='google')
        
        # Get category URLs
        categories = get_wikiquote_author_categories().get(language, [])
        
        all_authors = set()
        
        # Scrape each category
        for category_url in categories:
            logger.info(f"Scraping {language} category: {category_url}")
            authors = scrape_author_index_page(scraper, category_url, max_pages=5)
            all_authors.update(authors)
            time.sleep(settings.scrape_delay)
        
        stats["authors_found"] = len(all_authors)
        logger.info(f"Found {len(all_authors)} authors from {language} WikiQuote")
        
        if limit:
            all_authors = list(all_authors)[:limit]
            logger.info(f"Limited to {limit} authors")
        
        # Create or update authors
        for author_name in all_authors:
            try:
                # Determine which name field to use
                name_en = None
                name_ru = None
                
                if language == "en":
                    name_en = author_name
                    # Try to find Russian version
                    # Check if author page has Russian link
                    author_url = scraper.get_author_url(author_name)
                    soup = scraper.fetch_page(author_url)
                    if soup:
                        # Look for Russian language link
                        ru_link = soup.find("a", {"lang": "ru", "hreflang": "ru"})
                        if ru_link:
                            ru_url = ru_link.get("href")
                            if ru_url and "ru.wikiquote.org" in ru_url:
                                # Extract Russian author name from URL
                                ru_name = ru_url.split("/wiki/")[-1].replace("_", " ")
                                name_ru = ru_name
                        else:
                            # Try to translate
                            try:
                                translated = translator.translate(
                                    author_name, source_lang='en', target_lang='ru'
                                )
                                if translated:
                                    name_ru = translated
                            except Exception as e:
                                logger.debug(f"Could not translate {author_name}: {e}")
                else:  # language == "ru"
                    name_ru = author_name
                    # Try to find English version
                    author_url = scraper.get_author_url(author_name)
                    soup = scraper.fetch_page(author_url)
                    if soup:
                        # Look for English language link
                        en_link = soup.find("a", {"lang": "en", "hreflang": "en"})
                        if en_link:
                            en_url = en_link.get("href")
                            if en_url and "en.wikiquote.org" in en_url:
                                # Extract English author name from URL
                                en_name = en_url.split("/wiki/")[-1].replace("_", " ")
                                name_en = en_name
                        else:
                            # Try to translate
                            try:
                                translated = translator.translate(
                                    author_name, source_lang='ru', target_lang='en'
                                )
                                if translated:
                                    name_en = translated
                            except Exception as e:
                                logger.debug(f"Could not translate {author_name}: {e}")
                
                # Get or create author
                existing_author = None
                if name_en:
                    existing_author = (
                        db.query(Author)
                        .filter(Author.name_en == name_en)
                        .first()
                    )
                if not existing_author and name_ru:
                    existing_author = (
                        db.query(Author)
                        .filter(Author.name_ru == name_ru)
                        .first()
                    )
                
                if existing_author:
                    # Update missing name fields
                    updated = False
                    if name_en and not existing_author.name_en:
                        existing_author.name_en = name_en
                        updated = True
                    if name_ru and not existing_author.name_ru:
                        existing_author.name_ru = name_ru
                        updated = True
                    if updated and not dry_run:
                        db.commit()
                    stats["authors_existing"] += 1
                else:
                    # Create new author
                    if dry_run:
                        logger.info(
                            f"Would create author: name_en='{name_en}', "
                            f"name_ru='{name_ru}'"
                        )
                        author = None  # For dry run, we can't load quotes
                    else:
                        author = author_repo.create(
                            name_en=name_en,
                            name_ru=name_ru,
                            bio=None,
                            wikiquote_url=scraper.get_author_url(author_name)
                        )
                    stats["authors_created"] += 1
                    
                    # Load up to 5 quotes for newly created authors
                    if not dry_run and author:
                        quote_stats = load_quotes_for_author(
                            author, scraper, db, language, max_quotes=5
                        )
                        stats["quotes_loaded"] = stats.get("quotes_loaded", 0) + \
                                                 quote_stats.get("quotes_loaded", 0)
                        stats["quotes_rejected"] = stats.get("quotes_rejected", 0) + \
                                                   quote_stats.get("quotes_rejected", 0)
                
                time.sleep(settings.scrape_delay * 0.5)  # Small delay between authors
                
            except Exception as e:
                logger.error(f"Error processing author {author_name}: {e}")
                stats["errors"] += 1
                continue
        
        return stats
        
    except Exception as e:
        logger.error(f"Error discovering authors: {e}")
        raise


def find_author_for_quote_via_search(
    quote: Quote,
    scraper,
    db
) -> Optional[Author]:
    """
    Try to find author using WikiQuote search.
    
    Uses WikiQuote's search functionality to find which page contains the quote.
    
    Args:
        quote: Quote to find author for
        scraper: WikiQuote scraper instance
        db: Database session
        
    Returns:
        Author if found, None otherwise
    """
    try:
        # Use WikiQuote search: https://en.wikiquote.org/wiki/Special:Search
        # Search for a unique snippet of the quote
        quote_snippet = quote.text[:50].strip()
        if len(quote_snippet) < 20:
            return None
        
        # Construct search URL
        search_url = f"{scraper.base_url}/wiki/Special:Search"
        # Use a POST request or construct GET URL with search parameter
        # WikiQuote uses ?search= parameter
        search_params = {
            "search": quote_snippet,
            "go": "Go"  # "Go" button does exact page match
        }
        
        # Try to search
        soup = scraper.fetch_page(
            f"{search_url}?search={quote_snippet.replace(' ', '+')}"
        )
        
        if soup:
            # Look for search results
            # WikiQuote search results are typically in <ul class="mw-search-results">
            results = soup.find("ul", class_="mw-search-results")
            if results:
                # Get first result
                first_result = results.find("li")
                if first_result:
                    link = first_result.find("a")
                    if link:
                        page_url = link.get("href")
                        if page_url:
                            if not page_url.startswith("http"):
                                page_url = scraper.base_url + page_url
                            
                            # Extract author name from URL
                            # URL format: /wiki/Author_Name
                            author_name = page_url.split("/wiki/")[-1].replace("_", " ")
                            
                            # Find or create author
                            author_repo = AuthorRepository(db)
                            
                            # Determine name fields
                            name_en = None
                            name_ru = None
                            if quote.language == "en":
                                name_en = author_name
                            else:
                                name_ru = author_name
                            
                            author = author_repo.get_or_create(
                                name_en=name_en,
                                name_ru=name_ru
                            )
                            
                            # Verify quote is on this author's page
                            data = scraper.scrape_author_page(author_name)
                            for scraped_quote in data.get("quotes", []):
                                if quote.text.strip() == scraped_quote.strip():
                                    logger.info(
                                        f"Found author {author.id} ({author_name}) "
                                        f"for quote {quote.id} via search"
                                    )
                                    return author
        
        return None
        
    except Exception as e:
        logger.debug(f"Search failed for quote {quote.id}: {e}")
        return None


def find_author_for_quote(
    quote: Quote,
    db,
    en_scraper: WikiQuoteEnScraper,
    ru_scraper: WikiQuoteRuScraper,
    dry_run: bool = False
) -> Optional[Author]:
    """
    Use reverse lookup to find which author a quote belongs to.
    
    Tries multiple strategies:
    1. WikiQuote search (fast)
    2. Check recently discovered authors (medium speed)
    3. Full author list check (slow, last resort)
    
    Args:
        quote: Quote to find author for
        db: Database session
        en_scraper: English WikiQuote scraper
        ru_scraper: Russian WikiQuote scraper
        dry_run: If True, only report what would be done
        
    Returns:
        Author if found, None otherwise
    """
    try:
        # Use appropriate scraper based on quote language
        scraper = en_scraper if quote.language == "en" else ru_scraper
        
        # Strategy 1: Try WikiQuote search (fastest)
        author = find_author_for_quote_via_search(quote, scraper, db)
        if author:
            return author
        
        # Strategy 2: Check only authors that have quotes in the same language
        # This is more efficient than checking all authors
        authors_with_quotes = (
            db.query(Author)
            .join(Quote, Author.id == Quote.author_id)
            .filter(Quote.language == quote.language)
            .distinct()
            .limit(100)  # Limit to 100 most likely authors
            .all()
        )
        
        for author in authors_with_quotes:
            try:
                # Get author name for this language
                author_name = None
                if quote.language == "en" and author.name_en:
                    author_name = author.name_en
                elif quote.language == "ru" and author.name_ru:
                    author_name = author.name_ru
                
                if not author_name:
                    continue
                
                # Scrape author page
                data = scraper.scrape_author_page(author_name)
                
                # Check if quote text matches any quote from this author
                for scraped_quote in data.get("quotes", []):
                    if quote.text.strip() == scraped_quote.strip():
                        logger.info(
                            f"Found author {author.id} ({author_name}) "
                            f"for quote {quote.id}"
                        )
                        return author
                
                time.sleep(settings.scrape_delay)
                
            except Exception as e:
                logger.debug(f"Error checking author {author.id}: {e}")
                continue
        
        return None
        
    except Exception as e:
        logger.error(f"Error finding author for quote {quote.id}: {e}")
        return None


def link_orphaned_quotes(
    db,
    dry_run: bool = False,
    limit: Optional[int] = None
) -> Dict[str, int]:
    """
    Link orphaned quotes to authors using reverse lookup.
    
    Args:
        db: Database session
        dry_run: If True, only report what would be done
        limit: Limit number of quotes to process
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "quotes_checked": 0,
        "quotes_linked": 0,
        "quotes_not_found": 0,
        "errors": 0
    }
    
    try:
        # Get orphaned quotes
        orphaned_quotes = (
            db.query(Quote)
            .filter(Quote.author_id.is_(None))
            .all()
        )
        
        if limit:
            orphaned_quotes = orphaned_quotes[:limit]
        
        stats["quotes_checked"] = len(orphaned_quotes)
        logger.info(f"Checking {len(orphaned_quotes)} orphaned quotes")
        
        en_scraper = WikiQuoteEnScraper()
        ru_scraper = WikiQuoteRuScraper()
        
        for quote in orphaned_quotes:
            try:
                author = find_author_for_quote(
                    quote, db, en_scraper, ru_scraper, dry_run
                )
                
                if author:
                    if not dry_run:
                        quote.author_id = author.id
                        db.commit()
                    stats["quotes_linked"] += 1
                else:
                    stats["quotes_not_found"] += 1
                
            except Exception as e:
                logger.error(f"Error processing quote {quote.id}: {e}")
                stats["errors"] += 1
                continue
        
        return stats
        
    except Exception as e:
        logger.error(f"Error linking orphaned quotes: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Discover authors from WikiQuote and link orphaned quotes"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done, don't make changes"
    )
    parser.add_argument(
        "--limit-authors",
        type=int,
        default=None,
        help="Limit number of authors to discover (default: all)"
    )
    parser.add_argument(
        "--limit-quotes",
        type=int,
        default=None,
        help="Limit number of orphaned quotes to process (default: all)"
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip scraping author index pages"
    )
    parser.add_argument(
        "--skip-quotes",
        action="store_true",
        help="Skip linking orphaned quotes"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Discovering authors from WikiQuote")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    db = SessionLocal()
    
    try:
        # Step 1: Discover authors from index pages
        if not args.skip_index:
            logger.info("\nStep 1: Discovering authors from WikiQuote index pages...")
            total_quote_stats = {"quotes_loaded": 0, "quotes_rejected": 0}
            for language in ["en", "ru"]:
                logger.info(f"\nProcessing {language} authors...")
                stats = discover_authors_from_index(
                    db, language, args.dry_run, args.limit_authors
                )
                logger.info(f"  Found: {stats['authors_found']}")
                logger.info(f"  Created: {stats['authors_created']}")
                logger.info(f"  Existing: {stats['authors_existing']}")
                logger.info(f"  Quotes loaded: {stats.get('quotes_loaded', 0)}")
                logger.info(f"  Quotes rejected: {stats.get('quotes_rejected', 0)}")
                logger.info(f"  Errors: {stats['errors']}")
                total_quote_stats["quotes_loaded"] += stats.get("quotes_loaded", 0)
                total_quote_stats["quotes_rejected"] += stats.get("quotes_rejected", 0)
            logger.info(
                f"\nTotal quotes loaded: {total_quote_stats['quotes_loaded']}, "
                f"rejected: {total_quote_stats['quotes_rejected']}"
            )
        else:
            logger.info("Skipping author index scraping")
        
        # Step 2: Link orphaned quotes
        if not args.skip_quotes:
            logger.info("\nStep 2: Linking orphaned quotes to authors...")
            stats = link_orphaned_quotes(db, args.dry_run, args.limit_quotes)
            logger.info(f"  Checked: {stats['quotes_checked']}")
            logger.info(f"  Linked: {stats['quotes_linked']}")
            logger.info(f"  Not found: {stats['quotes_not_found']}")
            logger.info(f"  Errors: {stats['errors']}")
        else:
            logger.info("Skipping orphaned quote linking")
        
        logger.info("\n" + "=" * 60)
        logger.info("Discovery completed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error in discovery process: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

