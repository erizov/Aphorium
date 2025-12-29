"""
Script to delete quotes that are not English or Russian.
Only 'en' and 'ru' quotes should remain in the table.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote
from logger_config import logger


def delete_non_en_ru_quotes(dry_run: bool = True):
    """
    Delete quotes that are not English ('en') or Russian ('ru').
    
    Args:
        dry_run: If True, only report what would be deleted
    """
    db = SessionLocal()
    
    try:
        # Get all quotes
        all_quotes = db.query(Quote).all()
        logger.info(f"Total quotes in database: {len(all_quotes)}")
        
        # Find non-EN/RU quotes
        non_en_ru_quotes = [
            q for q in all_quotes 
            if q.language not in ['en', 'ru']
        ]
        
        logger.info(f"Found {len(non_en_ru_quotes)} quotes that are not EN or RU")
        
        if dry_run:
            logger.info("DRY RUN - No quotes will be deleted")
            # Group by language
            from collections import Counter
            lang_counts = Counter([q.language for q in non_en_ru_quotes])
            logger.info(f"Languages to delete: {dict(lang_counts)}")
            
            # Show examples
            for quote in non_en_ru_quotes[:10]:
                preview = quote.text[:80].replace('\n', ' ')
                logger.info(
                    f"  Would delete: [{quote.id}] lang={quote.language} "
                    f"{preview}..."
                )
            if len(non_en_ru_quotes) > 10:
                logger.info(f"  ... and {len(non_en_ru_quotes) - 10} more")
        else:
            # Delete non-EN/RU quotes
            deleted_count = 0
            for quote in non_en_ru_quotes:
                try:
                    db.delete(quote)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete quote {quote.id}: {e}")
            
            db.commit()
            logger.info(f"Deleted {deleted_count} non-EN/RU quotes")
            
            # Show final counts
            en_count = db.query(Quote).filter(Quote.language == 'en').count()
            ru_count = db.query(Quote).filter(Quote.language == 'ru').count()
            logger.info(f"Remaining quotes: EN={en_count}, RU={ru_count}")
        
        return len(non_en_ru_quotes)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Delete quotes that are not English or Russian"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete the quotes (default: dry-run)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Delete Non-EN/RU Quotes")
    logger.info("=" * 60)
    
    count = delete_non_en_ru_quotes(dry_run=not args.execute)
    
    logger.info("=" * 60)
    logger.info(f"Total non-EN/RU quotes: {count}")
    if not args.execute:
        logger.info("\nTo actually delete quotes, run with --execute flag")
    logger.info("=" * 60)

