"""
Drop the sources_metadata table from the database.

This script removes the unused sources_metadata table to simplify the schema.

Usage:
    python scripts/drop_sources_metadata_table.py [--dry-run]
"""

import sys
import argparse
from pathlib import Path
from sqlalchemy import text, inspect

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal, engine
from logger_config import logger


def drop_sources_metadata_table(dry_run: bool = False) -> None:
    """
    Drop the sources_metadata table.
    
    Args:
        dry_run: If True, only report what would be done
    """
    db = SessionLocal()
    
    try:
        # Check if table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'sources_metadata' not in tables:
            logger.info("Table 'sources_metadata' does not exist. Nothing to do.")
            return
        
        # Check row count
        result = db.execute(text("SELECT COUNT(*) FROM sources_metadata"))
        row_count = result.scalar()
        
        logger.info(f"Table 'sources_metadata' exists with {row_count} rows")
        
        if dry_run:
            logger.info("DRY RUN - Would drop table 'sources_metadata'")
            return
        
        # Drop the table
        logger.info("Dropping table 'sources_metadata'...")
        db.execute(text("DROP TABLE IF EXISTS sources_metadata"))
        db.commit()
        
        logger.info("✅ Successfully dropped table 'sources_metadata'")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error dropping table: {e}")
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Drop the sources_metadata table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done, don't make changes"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Dropping sources_metadata table")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    drop_sources_metadata_table(dry_run=args.dry_run)
    
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

