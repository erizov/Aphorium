"""
Helper script to match translations between English and Russian quotes.

Usage:
    python match_translations.py
    python match_translations.py --author-id 1
"""

import argparse
from database import SessionLocal
from scrapers.matcher import TranslationMatcher
from logger_config import logger


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Match translations between quotes"
    )
    parser.add_argument(
        "--author-id",
        type=int,
        help="Match quotes for specific author ID"
    )

    args = parser.parse_args()

    db = SessionLocal()
    matcher = TranslationMatcher(db)

    try:
        if args.author_id:
            logger.info(f"Matching translations for author {args.author_id}")
            matches = matcher.match_quotes_by_author(args.author_id)
            logger.info(f"Created {matches} translation matches")
        else:
            logger.info("Matching translations for all authors")
            matches = matcher.match_all_authors()
            logger.info(f"Created {matches} translation matches total")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to match translations: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

