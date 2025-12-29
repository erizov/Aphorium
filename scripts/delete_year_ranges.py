"""
Script to delete quotes containing author year ranges like (1828—1910).
"""

import re
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote
from logger_config import logger


def find_and_delete_year_ranges(dry_run: bool = True):
    """
    Find and delete quotes containing year ranges like (1828—1910).
    
    Args:
        dry_run: If True, only report what would be deleted
    """
    db = SessionLocal()
    
    # Pattern to match year ranges: (1828—1910), (1828-1910), (1828–1910)
    # Supports em dash (—), en dash (–), and hyphen (-)
    pattern = r'\(\d{4}[\s]*[—–-][\s]*\d{4}\)'
    
    try:
        quotes = db.query(Quote).all()
        logger.info(f"Checking {len(quotes)} quotes for year ranges...")
        
        matches = []
        for quote in quotes:
            if re.search(pattern, quote.text):
                matches.append((quote.id, quote.text))
        
        logger.info(f"Found {len(matches)} quotes with year ranges")
        
        if dry_run:
            logger.info("DRY RUN - No quotes will be deleted")
            for quote_id, text in matches[:20]:
                # Extract the year range for display
                match = re.search(pattern, text)
                year_range = match.group(0) if match else ""
                preview = text[:80].replace('\n', ' ')
                logger.info(f"  Would delete: [{quote_id}] {preview}... (contains {year_range})")
            if len(matches) > 20:
                logger.info(f"  ... and {len(matches) - 20} more")
        else:
            # Delete quotes with year ranges
            deleted_count = 0
            for quote_id, text in matches:
                try:
                    quote = db.query(Quote).filter(Quote.id == quote_id).first()
                    if quote:
                        db.delete(quote)
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete quote {quote_id}: {e}")
            
            db.commit()
            logger.info(f"Deleted {deleted_count} quotes with year ranges")
        
        return len(matches)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Delete quotes containing author year ranges"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete the quotes (default: dry-run)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Delete Quotes with Year Ranges")
    logger.info("=" * 60)
    
    count = find_and_delete_year_ranges(dry_run=not args.execute)
    
    logger.info("=" * 60)
    logger.info(f"Total quotes with year ranges: {count}")
    if not args.execute:
        logger.info("\nTo actually delete quotes, run with --execute flag")
    logger.info("=" * 60)

