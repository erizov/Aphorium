"""
Main ingestion script for WikiQuote data.

Usage:
    python -m scrapers.ingest --lang en --author "William Shakespeare"
    python -m scrapers.ingest --lang ru --author "Александр Пушкин"
"""

import argparse
from sqlalchemy.orm import Session

from database import SessionLocal, init_db
from scrapers.wikiquote_en import WikiQuoteEnScraper
from scrapers.wikiquote_ru import WikiQuoteRuScraper
from repositories.author_repository import AuthorRepository
from repositories.source_repository import SourceRepository
from repositories.quote_repository import QuoteRepository
from logger_config import logger


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
        author = author_repo.get_or_create(
            name=data["author_name"],
            language=language,
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

            # Create quotes
            for quote_text in quotes:
                try:
                    quote_repo.create(
                        text=quote_text,
                        author_id=author.id,
                        source_id=source.id,
                        language=language
                    )
                except Exception as e:
                    logger.warning(f"Failed to create quote: {e}")
                    continue

        # Process quotes without source
        for quote_text in data["quotes"]:
            # Skip if already processed (in sources)
            if quote_text not in [
                q for quotes_list in data["sources"].values()
                for q in quotes_list
            ]:
                try:
                    quote_repo.create(
                        text=quote_text,
                        author_id=author.id,
                        source_id=None,
                        language=language
                    )
                except Exception as e:
                    logger.warning(f"Failed to create quote: {e}")
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

