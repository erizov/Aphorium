"""
Finalize author schema: ensure all authors have both name_en and name_ru, then drop columns.

This script:
1. Ensures standalone authors have both name_en and name_ru
2. Drops name and language columns (SQLite-compatible)
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import engine, SessionLocal
from sqlalchemy import text
from logger_config import logger


def ensure_all_authors_have_both_names(db):
    """Ensure all authors have both name_en and name_ru."""
    logger.info("Ensuring all authors have both name_en and name_ru...")
    
    # Get authors missing name_en
    missing_en = db.execute(
        text("SELECT id, name, name_ru FROM authors WHERE name_en IS NULL")
    ).fetchall()
    
    # Get authors missing name_ru
    missing_ru = db.execute(
        text("SELECT id, name, name_en FROM authors WHERE name_ru IS NULL")
    ).fetchall()
    
    logger.info(f"Authors missing name_en: {len(missing_en)}")
    logger.info(f"Authors missing name_ru: {len(missing_ru)}")
    
    # For authors missing name_en, use name if available
    for row in missing_en:
        author_id, name, name_ru = row
        if name:
            db.execute(
                text("UPDATE authors SET name_en=:name WHERE id=:id"),
                {"name": name, "id": author_id}
            )
            logger.debug(f"Set name_en for author {author_id}: '{name}'")
    
    # For authors missing name_ru, use name if available
    for row in missing_ru:
        author_id, name, name_en = row
        if name:
            db.execute(
                text("UPDATE authors SET name_ru=:name WHERE id=:id"),
                {"name": name, "id": author_id}
            )
            logger.debug(f"Set name_ru for author {author_id}: '{name}'")
    
    db.commit()
    logger.info("✅ All authors now have both name_en and name_ru")


def drop_columns_sqlite(db):
    """Drop name and language columns using SQLite-compatible method."""
    logger.info("Dropping 'name' and 'language' columns (SQLite method)...")
    
    try:
        # SQLite doesn't support DROP COLUMN, so we need to recreate the table
        # Step 1: Create new table without name and language
        db.execute(text("""
            CREATE TABLE authors_new (
                id INTEGER PRIMARY KEY,
                name_en VARCHAR(255),
                name_ru VARCHAR(255),
                bio TEXT,
                wikiquote_url VARCHAR(500),
                created_at TIMESTAMP
            )
        """))
        
        # Step 2: Copy data
        db.execute(text("""
            INSERT INTO authors_new (id, name_en, name_ru, bio, wikiquote_url, created_at)
            SELECT id, name_en, name_ru, bio, wikiquote_url, created_at
            FROM authors
        """))
        
        # Step 3: Drop old table
        db.execute(text("DROP TABLE authors"))
        
        # Step 4: Rename new table
        db.execute(text("ALTER TABLE authors_new RENAME TO authors"))
        
        # Step 5: Recreate indexes
        db.execute(text("CREATE INDEX IF NOT EXISTS ix_authors_id ON authors(id)"))
        
        db.commit()
        logger.info("✅ Successfully dropped 'name' and 'language' columns")
        
    except Exception as e:
        logger.error(f"Error dropping columns: {e}", exc_info=True)
        db.rollback()
        raise


def drop_columns_postgresql(db):
    """Drop name and language columns (PostgreSQL method)."""
    logger.info("Dropping 'name' and 'language' columns (PostgreSQL method)...")
    
    try:
        db.execute(text("ALTER TABLE authors DROP COLUMN IF EXISTS name"))
        db.execute(text("ALTER TABLE authors DROP COLUMN IF EXISTS language"))
        db.commit()
        logger.info("✅ Successfully dropped 'name' and 'language' columns")
        
    except Exception as e:
        logger.error(f"Error dropping columns: {e}", exc_info=True)
        db.rollback()
        raise


def finalize_author_schema():
    """Finalize author schema."""
    db = SessionLocal()
    
    try:
        # Check database type
        is_sqlite = 'sqlite' in str(engine.url).lower()
        
        # Step 1: Ensure all authors have both names
        ensure_all_authors_have_both_names(db)
        
        # Step 2: Drop columns
        if is_sqlite:
            drop_columns_sqlite(db)
        else:
            drop_columns_postgresql(db)
        
        # Step 3: Verify
        total = db.execute(text("SELECT COUNT(*) FROM authors")).scalar()
        with_both = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE name_en IS NOT NULL AND name_ru IS NOT NULL")
        ).scalar()
        
        logger.info("=" * 60)
        logger.info("Final verification:")
        logger.info(f"  Total authors: {total}")
        logger.info(f"  Authors with both name_en and name_ru: {with_both}")
        logger.info("=" * 60)
        
        if with_both == total:
            logger.info("✅ All authors have both name_en and name_ru!")
        else:
            logger.warning(f"⚠️  {total - with_both} authors missing name_en or name_ru")
        
    except Exception as e:
        logger.error(f"Error finalizing schema: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Finalizing author schema")
    logger.info("=" * 60)
    
    finalize_author_schema()
    
    logger.info("=" * 60)
    logger.info("Complete!")
    logger.info("=" * 60)

