"""
Script to clear all quotes from the database for reloading.

WARNING: This will delete ALL quotes from the database.
Use this before reloading with new strict validation.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote, QuoteTranslation
from logger_config import logger


def clear_all_quotes() -> dict:
    """
    Clear all quotes and translations from the database.
    
    Returns:
        Dictionary with statistics
    """
    db = SessionLocal()
    stats = {
        "quotes_deleted": 0,
        "translations_deleted": 0
    }
    
    try:
        # Count before deletion
        quote_count = db.query(Quote).count()
        translation_count = db.query(QuoteTranslation).count()
        
        logger.info(f"Found {quote_count} quotes and {translation_count} translations")
        logger.warning("DELETING ALL QUOTES AND TRANSLATIONS...")
        
        # Delete all translations first (foreign key constraint)
        deleted_translations = db.query(QuoteTranslation).delete()
        stats["translations_deleted"] = deleted_translations
        
        # Delete all quotes
        deleted_quotes = db.query(Quote).delete()
        stats["quotes_deleted"] = deleted_quotes
        
        db.commit()
        
        logger.info(f"Deleted {stats['quotes_deleted']} quotes")
        logger.info(f"Deleted {stats['translations_deleted']} translations")
        logger.info("Database cleared. Ready for reloading.")
        
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to clear quotes: {e}")
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clear all quotes from database (for reloading)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion (required for safety)"
    )
    
    args = parser.parse_args()
    
    if not args.confirm:
        logger.error("=" * 60)
        logger.error("WARNING: This will delete ALL quotes from the database!")
        logger.error("=" * 60)
        logger.error("To confirm, run with --confirm flag:")
        logger.error("  python scripts/clear_all_quotes.py --confirm")
        return
    
    logger.info("=" * 60)
    logger.info("Clearing All Quotes")
    logger.info("=" * 60)
    
    stats = clear_all_quotes()
    
    logger.info("=" * 60)
    logger.info("Summary:")
    logger.info(f"  Quotes deleted: {stats['quotes_deleted']}")
    logger.info(f"  Translations deleted: {stats['translations_deleted']}")
    logger.info("=" * 60)
    logger.info("Database is now empty. Ready for reloading with new validation.")


if __name__ == "__main__":
    main()

