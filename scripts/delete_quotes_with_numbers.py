"""
Delete quotes that contain any numbers in the text column.

This script finds and deletes quotes containing:
- Arabic numerals (0-9)
- Roman numerals (I, II, III, IV, V, etc.)
- Any numeric characters

Usage:
    python scripts/delete_quotes_with_numbers.py [--dry-run] [--limit N]
"""

import sys
import argparse
import re
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote, QuoteTranslation
from logger_config import logger


def has_numbers(text: str) -> bool:
    """
    Check if text contains any numbers.
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains any numbers
    """
    if not text:
        return False
    
    # Check for Arabic numerals (0-9)
    if re.search(r'\d', text):
        return True
    
    # Check for Roman numerals - be more precise to avoid false positives
    # Only match actual Roman numerals, not just "I" as a pronoun
    # Patterns that indicate Roman numerals:
    # - Multiple I's together: II, III, IV, VI, VII, VIII, IX
    # - In parentheses: (I), (II), (III), (IV), (V)
    # - After specific words: Act I, Chapter II, Part III
    # - Standalone with word boundaries: \bII\b, \bIII\b, etc.
    
    # Match Roman numerals that are clearly numbers (not single "I")
    roman_patterns = [
        r'\b[IVX]{2,}\b',  # Two or more Roman numeral characters (II, III, IV, VI, etc.)
        r'\([IVX]+\)',  # Roman in parentheses: (I), (II), (III), (IV), (V)
        r'\b(?:Act|Chapter|Part|Section|Article|Scene|Сцена|Глава|Часть|Раздел)\s+[IVX]+\b',  # After keywords
        r'[IVX]+[,\s]+(?:Act|Chapter|Part|Section)',  # Before keywords
        r'\b[IVXLCDM]{3,}\b',  # Three or more extended Roman characters
    ]
    for pattern in roman_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def delete_quotes_with_numbers(
    dry_run: bool = False,
    limit: int = None
) -> dict:
    """
    Delete quotes that contain any numbers.
    
    Args:
        dry_run: If True, only report what would be done
        limit: Limit number of quotes to check (None for all)
        
    Returns:
        Dictionary with statistics
    """
    db = SessionLocal()
    stats = {
        "quotes_checked": 0,
        "quotes_with_numbers": 0,
        "quotes_deleted": 0,
        "errors": 0
    }
    
    try:
        # Get all quotes
        quotes = db.query(Quote).all()
        
        if limit:
            quotes = quotes[:limit]
        
        stats["quotes_checked"] = len(quotes)
        logger.info(f"Checking {len(quotes)} quotes for numbers...")
        
        quotes_to_delete = []
        
        for quote in quotes:
            try:
                if has_numbers(quote.text):
                    quotes_to_delete.append(quote)
                    stats["quotes_with_numbers"] += 1
                    
                    if stats["quotes_with_numbers"] <= 10:
                        # Show first 10 examples
                        preview = quote.text[:60] + "..." if len(quote.text) > 60 else quote.text
                        logger.info(
                            f"Quote {quote.id} contains numbers: {preview}"
                        )
            except Exception as e:
                logger.error(f"Error checking quote {quote.id}: {e}")
                stats["errors"] += 1
                continue
        
        logger.info(f"Found {len(quotes_to_delete)} quotes with numbers")
        
        if dry_run:
            logger.info("DRY RUN - Would delete these quotes")
        else:
            # Get quote IDs
            quote_ids = [q.id for q in quotes_to_delete]
            
            # Delete related QuoteTranslation records first
            translations_deleted = db.query(QuoteTranslation).filter(
                (QuoteTranslation.quote_id.in_(quote_ids)) |
                (QuoteTranslation.translated_quote_id.in_(quote_ids))
            ).delete(synchronize_session=False)
            
            logger.info(
                f"Deleted {translations_deleted} related translation records"
            )
            
            # Delete quotes
            for quote in quotes_to_delete:
                try:
                    db.delete(quote)
                    stats["quotes_deleted"] += 1
                except Exception as e:
                    logger.error(f"Error deleting quote {quote.id}: {e}")
                    stats["errors"] += 1
            
            if stats["quotes_deleted"] > 0:
                db.commit()
                logger.info(f"Deleted {stats['quotes_deleted']} quotes")
        
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting quotes: {e}")
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Delete quotes containing numbers"
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
        help="Limit number of quotes to check (default: all)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Deleting quotes with numbers")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    stats = delete_quotes_with_numbers(
        dry_run=args.dry_run,
        limit=args.limit
    )
    
    logger.info("=" * 60)
    logger.info("Deletion completed!")
    logger.info(f"Quotes checked: {stats['quotes_checked']}")
    logger.info(f"Quotes with numbers: {stats['quotes_with_numbers']}")
    logger.info(f"Quotes deleted: {stats['quotes_deleted']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

