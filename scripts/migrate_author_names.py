"""
Database migration: Add name_en and name_ru columns to authors table.

This script adds the new columns if they don't exist.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import engine, Base
from sqlalchemy import text
from logger_config import logger


def migrate_author_names():
    """
    Add name_en and name_ru columns to authors table if they don't exist.
    """
    try:
        is_sqlite = 'sqlite' in str(engine.url).lower()
        
        with engine.connect() as conn:
            if is_sqlite:
                # SQLite: Check if columns exist, add if not
                try:
                    # Try to select from the columns - if they don't exist, will raise error
                    conn.execute(text("SELECT name_en, name_ru FROM authors LIMIT 1"))
                    logger.info("Columns name_en and name_ru already exist")
                except Exception:
                    # Columns don't exist, add them
                    logger.info("Adding name_en and name_ru columns to authors table...")
                    conn.execute(text("ALTER TABLE authors ADD COLUMN name_en VARCHAR(255)"))
                    conn.execute(text("ALTER TABLE authors ADD COLUMN name_ru VARCHAR(255)"))
                    conn.commit()
                    logger.info("✅ Added name_en and name_ru columns")
            else:
                # PostgreSQL: Check and add columns
                logger.info("Checking for name_en and name_ru columns...")
                
                # Check if name_en exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='authors' AND column_name='name_en'
                """))
                name_en_exists = result.fetchone() is not None
                
                # Check if name_ru exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='authors' AND column_name='name_ru'
                """))
                name_ru_exists = result.fetchone() is not None
                
                if name_en_exists and name_ru_exists:
                    logger.info("Columns name_en and name_ru already exist")
                else:
                    if not name_en_exists:
                        logger.info("Adding name_en column...")
                        conn.execute(text("ALTER TABLE authors ADD COLUMN name_en VARCHAR(255)"))
                        conn.commit()
                    
                    if not name_ru_exists:
                        logger.info("Adding name_ru column...")
                        conn.execute(text("ALTER TABLE authors ADD COLUMN name_ru VARCHAR(255)"))
                        conn.commit()
                    
                    logger.info("✅ Added name_en and name_ru columns")
        
        logger.info("Migration complete!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Migrating authors table: Adding name_en and name_ru columns")
    logger.info("=" * 60)
    
    try:
        migrate_author_names()
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("Next step: Run 'python scripts/update_author_names.py' to populate the fields")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

