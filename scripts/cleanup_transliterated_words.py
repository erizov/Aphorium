"""
Cleanup script to delete transliterated word translations.

Deletes all word_translations records starting from ID 1073 where
transliteration was used instead of proper translations.
"""

import sys
import argparse
from pathlib import Path
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal, init_db
from models import WordTranslation
from logger_config import logger


def delete_transliterated_records(
    db: Session,
    start_id: int = 1073,
    dry_run: bool = False
) -> dict:
    """
    Delete word translation records starting from specified ID.
    
    Args:
        db: Database session
        start_id: Starting ID to delete from
        dry_run: If True, only count records without deleting
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "total_found": 0,
        "deleted": 0,
        "errors": []
    }
    
    try:
        # Count records to be deleted
        count = db.query(WordTranslation).filter(
            WordTranslation.id >= start_id
        ).count()
        
        stats["total_found"] = count
        
        if count == 0:
            logger.info(f"No records found with ID >= {start_id}")
            return stats
        
        logger.info(f"Found {count} records with ID >= {start_id}")
        
        if dry_run:
            logger.info("DRY RUN: Would delete these records")
            # Show sample records
            sample = db.query(WordTranslation).filter(
                WordTranslation.id >= start_id
            ).limit(10).all()
            
            logger.info("Sample records to be deleted:")
            for record in sample:
                logger.info(
                    f"  ID {record.id}: {record.word_en} -> {record.word_ru}"
                )
        else:
            # Delete records
            deleted = db.query(WordTranslation).filter(
                WordTranslation.id >= start_id
            ).delete(synchronize_session=False)
            
            db.commit()
            stats["deleted"] = deleted
            
            logger.info(f"Successfully deleted {deleted} records")
    
    except Exception as e:
        db.rollback()
        error_msg = f"Failed to delete records: {e}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)
        raise
    
    return stats


def reset_progress_file() -> None:
    """Reset word loading progress file to restart from beginning."""
    import json
    import os
    
    progress_file = "data/word_loading_progress.json"
    
    if os.path.exists(progress_file):
        progress = {
            "last_processed_index": 0,
            "total_loaded": 0,
            "batches_completed": 0,
            "errors": []
        }
        
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2)
        
        logger.info(f"Reset progress file: {progress_file}")
    else:
        logger.info("Progress file not found, nothing to reset")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Delete transliterated word translations"
    )
    parser.add_argument(
        "--start-id",
        type=int,
        default=1073,
        help="Starting ID to delete from (default: 1073)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Reset word loading progress file after deletion"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion (required unless --dry-run)"
    )
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    db = SessionLocal()
    
    try:
        if args.dry_run:
            logger.info("=" * 60)
            logger.info("DRY RUN MODE - No records will be deleted")
            logger.info("=" * 60)
        elif not args.confirm:
            logger.error("=" * 60)
            logger.error("WARNING: This will delete word translation records!")
            logger.error("=" * 60)
            logger.error(
                f"Records with ID >= {args.start_id} will be deleted."
            )
            logger.error("=" * 60)
            logger.error("To confirm, run with --confirm flag:")
            logger.error(
                f"  python scripts/cleanup_transliterated_words.py "
                f"--start-id {args.start_id} --confirm"
            )
            return
        
        logger.info("=" * 60)
        logger.info("Cleaning up transliterated word translations")
        logger.info("=" * 60)
        logger.info(f"Starting ID: {args.start_id}")
        logger.info(f"Dry run: {args.dry_run}")
        logger.info("=" * 60)
        
        # Delete records
        stats = delete_transliterated_records(
            db,
            start_id=args.start_id,
            dry_run=args.dry_run
        )
        
        logger.info("=" * 60)
        logger.info("CLEANUP COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Records found: {stats['total_found']}")
        logger.info(f"Records deleted: {stats['deleted']}")
        logger.info(f"Errors: {len(stats['errors'])}")
        logger.info("=" * 60)
        
        # Reset progress file if requested
        if args.reset_progress and not args.dry_run:
            reset_progress_file()
            logger.info(
                "Progress file reset. You can now reload words with "
                "proper translations."
            )
        
        if not args.dry_run and stats['deleted'] > 0:
            logger.info("")
            logger.info("Next steps:")
            logger.info(
                "1. Run: python load_10k_words_batch.py --reset"
            )
            logger.info(
                "   This will reload words with proper translations."
            )
    
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

