"""
Main ingestion script for WikiQuote data.

Usage:
    python -m scrapers.ingest --lang en --author "William Shakespeare"
    python -m scrapers.ingest --lang ru --author "Александр Пушкин"
"""

import argparse
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import SessionLocal, init_db
from scrapers.wikiquote_en import WikiQuoteEnScraper
from scrapers.wikiquote_ru import WikiQuoteRuScraper
from repositories.author_repository import AuthorRepository
from repositories.source_repository import SourceRepository
from repositories.quote_repository import QuoteRepository
from models import Quote
from logger_config import logger

# Try to import langdetect for language detection
try:
    from langdetect import detect, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


def detect_text_language(text: str) -> Optional[str]:
    """Detect language of text."""
    if not text or not text.strip():
        return None
    
    if HAS_LANGDETECT:
        try:
            lang = detect(text)
            if lang == 'en':
                return 'en'
            elif lang == 'ru':
                return 'ru'
        except LangDetectException:
            pass
    
    # Fallback: character-based detection
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
    has_latin = any(char.isalpha() and ord(char) < 128 for char in text)
    
    if has_cyrillic and not has_latin:
        return 'ru'
    elif has_latin and not has_cyrillic:
        return 'en'
    
    return None


def ingest_author(
    author_name: str,
    language: str,
    db: Session
) -> None:
    """
    Ingest quotes for an author from WikiQuote.

    Args:
        author_name: Author name
        language: Language code ('en' or 'ru')
        db: Database session
    """
    try:
        # Initialize scraper
        if language == "en":
            scraper = WikiQuoteEnScraper()
        elif language == "ru":
            scraper = WikiQuoteRuScraper()
        else:
            raise ValueError(f"Unsupported language: {language}")

        # Scrape author page
        logger.info(f"Scraping {language} WikiQuote for {author_name}")
        data = scraper.scrape_author_page(author_name)

        if not data["quotes"]:
            logger.warning(f"No quotes found for {author_name}")
            return

        # Create or get author
        author_repo = AuthorRepository(db)
        author_name_from_scraper = data["author_name"]
        
        # Determine which name field to use based on language
        name_en = None
        name_ru = None
        if language == "en":
            name_en = author_name_from_scraper
        else:  # language == "ru"
            name_ru = author_name_from_scraper
        
        # Get or create author using repository
        author = author_repo.get_or_create(
            name_en=name_en,
            name_ru=name_ru,
            bio=data["bio"],
            wikiquote_url=scraper.get_author_url(author_name)
        )

        # Create sources and quotes
        source_repo = SourceRepository(db)
        quote_repo = QuoteRepository(db)

        # Process quotes by source
        for source_title, quotes in data["sources"].items():
            # Create or get source
            source = source_repo.get_or_create(
                title=source_title,
                language=language,
                author_id=author.id,
                source_type="book"  # Default, could be improved
            )

            # Create quotes or attribute existing ones
            for quote_text in quotes:
                try:
                    # Check if quote already exists
                    existing_quote = (
                        db.query(Quote)
                        .filter(
                            Quote.text == quote_text,
                            Quote.language == language
                        )
                        .first()
                    )
                    
                    if existing_quote:
                        # Attribute existing quote to this author
                        if existing_quote.author_id != author.id:
                            logger.info(
                                f"Attributing existing quote (ID {existing_quote.id}) "
                                f"to author {author.id} ({author_name_from_scraper})"
                            )
                            existing_quote.author_id = author.id
                            existing_quote.source_id = source.id
                            db.commit()
                    else:
                        # Create new quote
                        quote_repo.create(
                            text=quote_text,
                            author_id=author.id,
                            source_id=source.id,
                            language=language
                        )
                except Exception as e:
                    logger.warning(f"Failed to create/attribute quote: {e}")
                    continue

        # Process quotes without source
        for quote_text in data["quotes"]:
            # Skip if already processed (in sources)
            if quote_text not in [
                q for quotes_list in data["sources"].values()
                for q in quotes_list
            ]:
                try:
                    # Check if quote already exists
                    existing_quote = (
                        db.query(Quote)
                        .filter(
                            Quote.text == quote_text,
                            Quote.language == language
                        )
                        .first()
                    )
                    
                    if existing_quote:
                        # Attribute existing quote to this author
                        if existing_quote.author_id != author.id:
                            logger.info(
                                f"Attributing existing quote (ID {existing_quote.id}) "
                                f"to author {author.id} ({author_name_from_scraper})"
                            )
                            existing_quote.author_id = author.id
                            db.commit()
                    else:
                        # Create new quote
                        quote_repo.create(
                            text=quote_text,
                            author_id=author.id,
                            source_id=None,
                            language=language
                        )
                except Exception as e:
                    logger.warning(f"Failed to create/attribute quote: {e}")
                    continue

        logger.info(
            f"Successfully ingested {len(data['quotes'])} quotes for "
            f"{author_name}"
        )

    except Exception as e:
        logger.error(f"Failed to ingest author {author_name}: {e}")
        raise


def main() -> None:
    """Main entry point for ingestion script."""
    parser = argparse.ArgumentParser(description="Ingest WikiQuote data")
    parser.add_argument(
        "--lang",
        required=True,
        choices=["en", "ru"],
        help="Language code"
    )
    parser.add_argument(
        "--author",
        required=True,
        help="Author name"
    )

    args = parser.parse_args()

    # Initialize database
    init_db()

    # Create database session
    db = SessionLocal()

    try:
        ingest_author(args.author, args.lang, db)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Ingestion failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

