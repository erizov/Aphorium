"""
Drop name and language columns from authors table.

This script:
1. Verifies all authors have both name_en and name_ru
2. Drops the name column
3. Drops the language column
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import engine, SessionLocal
from sqlalchemy import text
from logger_config import logger


def drop_author_columns():
    """Drop name and language columns from authors table."""
    db = SessionLocal()
    
    try:
        # Check if columns exist and verify data
        logger.info("Checking current state...")
        
        total = db.execute(text("SELECT COUNT(*) FROM authors")).scalar()
        with_name_en = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE name_en IS NOT NULL")
        ).scalar()
        with_name_ru = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE name_ru IS NOT NULL")
        ).scalar()
        
        logger.info(f"Total authors: {total}")
        logger.info(f"Authors with name_en: {with_name_en}")
        logger.info(f"Authors with name_ru: {with_name_ru}")
        
        if with_name_en < total or with_name_ru < total:
            logger.warning(
                f"⚠️  Some authors are missing name_en or name_ru. "
                f"Please merge authors first."
            )
            return
        
        # Check if columns exist
        is_sqlite = 'sqlite' in str(engine.url).lower()
        
        if is_sqlite:
            # SQLite: Check if columns exist
            try:
                db.execute(text("SELECT name, language FROM authors LIMIT 1"))
                columns_exist = True
            except Exception:
                columns_exist = False
                logger.info("Columns 'name' and 'language' do not exist")
            
            if columns_exist:
                logger.info("Dropping 'name' column...")
                # SQLite doesn't support DROP COLUMN directly, need to recreate table
                # This is complex, so we'll use a workaround
                logger.warning(
                    "SQLite doesn't support DROP COLUMN. "
                    "You'll need to recreate the table or use a migration tool."
                )
                logger.info("For now, we'll just verify the data is correct.")
            else:
                logger.info("Columns already dropped")
        else:
            # PostgreSQL: Can drop columns directly
            logger.info("Dropping 'name' column...")
            try:
                db.execute(text("ALTER TABLE authors DROP COLUMN IF EXISTS name"))
                db.commit()
                logger.info("✅ Dropped 'name' column")
            except Exception as e:
                logger.error(f"Error dropping 'name' column: {e}")
                db.rollback()
            
            logger.info("Dropping 'language' column...")
            try:
                db.execute(text("ALTER TABLE authors DROP COLUMN IF EXISTS language"))
                db.commit()
                logger.info("✅ Dropped 'language' column")
            except Exception as e:
                logger.error(f"Error dropping 'language' column: {e}")
                db.rollback()
        
        # Verify final state
        final_count = db.execute(text("SELECT COUNT(*) FROM authors")).scalar()
        logger.info(f"Final author count: {final_count}")
        
    except Exception as e:
        logger.error(f"Error dropping columns: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Dropping name and language columns from authors table")
    logger.info("=" * 60)
    
    drop_author_columns()
    
    logger.info("=" * 60)
    logger.info("Complete!")
    logger.info("=" * 60)

