"""
Script to delete quotes containing date patterns like (May 7, 2007) or (7 мая 2007).
"""

import re
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote
from logger_config import logger


def find_and_delete_date_patterns(dry_run: bool = True):
    """
    Find and delete quotes containing date patterns in English or Russian.
    
    Patterns matched:
    - English: (May 7, 2007), (May 7 2007), (7 May 2007), (May 2007), (2007)
    - Russian: (7 мая 2007), (7 мая 2007 г.), (май 2007), (2007)
    
    Args:
        dry_run: If True, only report what would be deleted
    """
    db = SessionLocal()
    
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
    
    # Date patterns
    date_patterns = [
        # English dates: (May 7, 2007), (May 7 2007), (7 May 2007)
        r'\([^)]*(?:' + '|'.join(english_months) + r')[^)]*\d{4}[^)]*\)',
        # English dates with day first: (7 May 2007)
        r'\(\d{1,2}\s+(?:' + '|'.join(english_months) + r')\s+\d{4}\)',
        # Russian dates: (7 мая 2007), (7 мая 2007 г.), (май 2007)
        r'\([^)]*(?:' + '|'.join(russian_months) + r')[^)]*\d{4}[^)]*\)',
        # Russian dates with day first: (7 мая 2007)
        r'\(\d{1,2}\s+(?:' + '|'.join(russian_months) + r')\s+\d{4}\)',
        # Year only: (2007)
        r'\(\d{4}\)',
    ]
    
    try:
        quotes = db.query(Quote).all()
        logger.info(f"Checking {len(quotes)} quotes for date patterns...")
        
        matches = []
        for quote in quotes:
            text = quote.text
            matched_pattern = None
            
            # Check each pattern
            for pattern in date_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    matched_pattern = pattern
                    matches.append((quote.id, text, matched_pattern))
                    break  # Only count once per quote
        
        logger.info(f"Found {len(matches)} quotes with date patterns")
        
        if dry_run:
            logger.info("DRY RUN - No quotes will be deleted")
            for quote_id, text, pattern in matches[:20]:
                # Extract the date for display
                date_match = None
                for p in date_patterns:
                    m = re.search(p, text, re.IGNORECASE)
                    if m:
                        date_match = m.group(0)
                        break
                
                preview = text[:80].replace('\n', ' ')
                logger.info(
                    f"  Would delete: [{quote_id}] {preview}... "
                    f"(contains {date_match})"
                )
            if len(matches) > 20:
                logger.info(f"  ... and {len(matches) - 20} more")
        else:
            # Delete quotes with date patterns
            deleted_count = 0
            for quote_id, text, pattern in matches:
                try:
                    quote = db.query(Quote).filter(Quote.id == quote_id).first()
                    if quote:
                        db.delete(quote)
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete quote {quote_id}: {e}")
            
            db.commit()
            logger.info(f"Deleted {deleted_count} quotes with date patterns")
        
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
        description="Delete quotes containing date patterns"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete the quotes (default: dry-run)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Delete Quotes with Date Patterns")
    logger.info("=" * 60)
    
    count = find_and_delete_date_patterns(dry_run=not args.execute)
    
    logger.info("=" * 60)
    logger.info(f"Total quotes with date patterns: {count}")
    if not args.execute:
        logger.info("\nTo actually delete quotes, run with --execute flag")
    logger.info("=" * 60)

