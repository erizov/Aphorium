"""
Delete all author rows with ID < 292.

This script:
1. Shows what will be deleted
2. Checks for quotes referencing these authors
3. Deletes the authors
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from sqlalchemy import text
from logger_config import logger


def delete_authors_before_id(min_id: int = 292, dry_run: bool = False):
    """Delete all authors with ID < min_id."""
    db = SessionLocal()
    
    try:
        # Check what will be deleted
        authors_to_delete = db.query(Author).filter(Author.id < min_id).all()
        count = len(authors_to_delete)
        
        logger.info("=" * 60)
        logger.info(f"Authors to delete (ID < {min_id}): {count}")
        logger.info("=" * 60)
        
        if count == 0:
            logger.info("No authors to delete")
            return
        
        # Check for quotes referencing these authors
        author_ids = [a.id for a in authors_to_delete]
        quotes_count = db.query(Quote).filter(Quote.author_id.in_(author_ids)).count()
        
        logger.info(f"Quotes referencing these authors: {quotes_count}")
        
        if quotes_count > 0:
            logger.warning(
                f"⚠️  {quotes_count} quotes reference these authors. "
                f"They will be orphaned (author_id will become NULL)."
            )
        
        if dry_run:
            logger.info("DRY RUN - No changes will be made")
            logger.info(f"Would delete {count} authors")
            return
        
        # Delete authors
        logger.info(f"Deleting {count} authors...")
        deleted = db.execute(
            text(f"DELETE FROM authors WHERE id < {min_id}")
        )
        db.commit()
        
        logger.info(f"✅ Deleted {deleted.rowcount} authors")
        
        # Verify
        remaining = db.query(Author).filter(Author.id < min_id).count()
        total = db.query(Author).count()
        
        logger.info("=" * 60)
        logger.info("Verification:")
        logger.info(f"  Authors with ID < {min_id}: {remaining}")
        logger.info(f"  Total authors remaining: {total}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error deleting authors: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Delete all authors with ID < 292'
    )
    parser.add_argument(
        '--min-id',
        type=int,
        default=292,
        help='Minimum author ID to keep (default: 292)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode - report what would be deleted without making changes'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info(f"Deleting authors with ID < {args.min_id}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    logger.info("=" * 60)
    
    delete_authors_before_id(min_id=args.min_id, dry_run=args.dry_run)
    
    logger.info("=" * 60)
    logger.info("Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

