"""
Attribute existing quotes to authors by scraping WikiQuote.

This script:
1. Gets all authors from the authors table (with name_en or name_ru)
2. For each author, scrapes their WikiQuote page
3. Matches scraped quotes to existing quotes in the database by text
4. Attributes matched quotes to the author

Usage:
    python scripts/attribute_quotes_to_authors.py [--lang en|ru|both] [--dry-run] [--limit N]
"""

import sys
import argparse
import time
from pathlib import Path
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote, Author
from scrapers.wikiquote_en import WikiQuoteEnScraper
from scrapers.wikiquote_ru import WikiQuoteRuScraper
from config import settings
from logger_config import logger


def scrape_and_attribute_quotes(
    author: Author,
    language: str,
    db: Session,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Scrape author's WikiQuote page and attribute matching quotes.
    
    Args:
        author: Author to process
        language: Language to scrape ('en' or 'ru')
        db: Database session
        dry_run: If True, only report what would be done
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "quotes_found": 0,
        "quotes_matched": 0,
        "quotes_attributed": 0,
        "errors": 0
    }
    
    # Get author name for this language
    author_name = None
    if language == "en" and author.name_en:
        author_name = author.name_en
    elif language == "ru" and author.name_ru:
        author_name = author.name_ru
    
    if not author_name:
        logger.debug(
            f"Skipping author {author.id}: no {language} name "
            f"(name_en='{author.name_en}', name_ru='{author.name_ru}')"
        )
        return stats
    
    try:
        # Initialize scraper
        if language == "en":
            scraper = WikiQuoteEnScraper()
        elif language == "ru":
            scraper = WikiQuoteRuScraper()
        else:
            logger.warning(f"Unsupported language: {language}")
            return stats
        
        # Scrape author page
        logger.info(
            f"Scraping {language} WikiQuote for {author_name} "
            f"(author ID: {author.id})"
        )
        data = scraper.scrape_author_page(author_name)
        
        if not data.get("quotes"):
            logger.warning(f"No quotes found for {author_name}")
            return stats
        
        stats["quotes_found"] = len(data["quotes"])
        
        # Collect all quote texts (from sources and general quotes)
        all_quote_texts = set(data["quotes"])
        for quotes_list in data.get("sources", {}).values():
            all_quote_texts.update(quotes_list)
        
        # Match scraped quotes to existing quotes
        for quote_text in all_quote_texts:
            # Find existing quote with same text and language
            existing_quote = (
                db.query(Quote)
                .filter(
                    Quote.text == quote_text,
                    Quote.language == language
                )
                .first()
            )
            
            if existing_quote:
                stats["quotes_matched"] += 1
                
                # Attribute quote to author if it doesn't have one or has wrong one
                if existing_quote.author_id != author.id:
                    if dry_run:
                        logger.info(
                            f"Would attribute quote {existing_quote.id} "
                            f"to author {author.id} ({author_name})"
                        )
                    else:
                        existing_quote.author_id = author.id
                        db.commit()
                        logger.debug(
                            f"Attributed quote {existing_quote.id} "
                            f"to author {author.id} ({author_name})"
                        )
                    stats["quotes_attributed"] += 1
        
        return stats
        
    except Exception as e:
        logger.error(f"Error processing author {author_name}: {e}")
        stats["errors"] += 1
        return stats


def attribute_quotes_to_authors(
    language: str = "both",
    dry_run: bool = False,
    limit: Optional[int] = None,
    author_delay: float = 0.5
) -> Dict[str, int]:
    """
    Attribute quotes to authors by scraping WikiQuote.
    
    Args:
        language: Language to process ('en', 'ru', or 'both')
        dry_run: If True, only report what would be done
        limit: Limit number of authors to process (None for all)
        
    Returns:
        Dictionary with statistics
    """
    db = SessionLocal()
    total_stats = {
        "authors_processed": 0,
        "authors_failed": 0,
        "quotes_found": 0,
        "quotes_matched": 0,
        "quotes_attributed": 0,
        "errors": 0
    }
    
    try:
        # Get all authors
        authors = db.query(Author).all()
        
        if limit:
            authors = authors[:limit]
        
        logger.info(f"Processing {len(authors)} authors")
        
        languages_to_process = []
        if language == "both":
            languages_to_process = ["en", "ru"]
        else:
            languages_to_process = [language]
        
        for author in authors:
            author_stats = {
                "quotes_found": 0,
                "quotes_matched": 0,
                "quotes_attributed": 0,
                "errors": 0
            }
            
            # Process each language
            for lang in languages_to_process:
                stats = scrape_and_attribute_quotes(
                    author, lang, db, dry_run
                )
                for key in author_stats:
                    author_stats[key] += stats[key]
                
                # Small delay between languages for same author
                if len(languages_to_process) > 1:
                    time.sleep(author_delay)
            
            # Update totals
            total_stats["quotes_found"] += author_stats["quotes_found"]
            total_stats["quotes_matched"] += author_stats["quotes_matched"]
            total_stats["quotes_attributed"] += author_stats["quotes_attributed"]
            total_stats["errors"] += author_stats["errors"]
            
            if author_stats["errors"] > 0:
                total_stats["authors_failed"] += 1
            else:
                total_stats["authors_processed"] += 1
            
            # Small delay between authors to avoid overwhelming the server
            if author_delay > 0:
                time.sleep(author_delay)
            
            # Log progress every 10 authors
            if total_stats["authors_processed"] % 10 == 0:
                logger.info(
                    f"Processed {total_stats['authors_processed']} authors, "
                    f"attributed {total_stats['quotes_attributed']} quotes"
                )
        
        return total_stats
        
    except Exception as e:
        logger.error(f"Error in attribution process: {e}")
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Attribute existing quotes to authors by scraping WikiQuote"
    )
    parser.add_argument(
        "--lang",
        choices=["en", "ru", "both"],
        default="both",
        help="Language to process (default: both)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done, don't make changes"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of authors to process (default: all)"
    )
    parser.add_argument(
        "--author-delay",
        type=float,
        default=0.5,
        help="Delay between processing authors in seconds (default: 0.5). "
             "Note: Each scraper request already has a 1.0s delay built-in."
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Attributing quotes to authors via WikiQuote")
    logger.info("=" * 60)
    logger.info(
        f"Rate limiting: {settings.scrape_delay}s per request "
        f"(built into scrapers) + {args.author_delay}s between authors"
    )
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    stats = attribute_quotes_to_authors(
        language=args.lang,
        dry_run=args.dry_run,
        limit=args.limit,
        author_delay=args.author_delay
    )
    
    logger.info("=" * 60)
    logger.info("Attribution completed!")
    logger.info(f"Authors processed: {stats['authors_processed']}")
    logger.info(f"Authors failed: {stats['authors_failed']}")
    logger.info(f"Quotes found on WikiQuote: {stats['quotes_found']}")
    logger.info(f"Quotes matched in database: {stats['quotes_matched']}")
    logger.info(f"Quotes attributed: {stats['quotes_attributed']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
