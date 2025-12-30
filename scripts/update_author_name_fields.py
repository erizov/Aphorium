"""
Update author name_en and name_ru fields from name based on language.

This script runs:
1. UPDATE authors SET name_en=name WHERE language='en'
2. UPDATE authors SET name_ru=name WHERE language='ru'
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from sqlalchemy import text
from logger_config import logger


def update_author_name_fields():
    """Update name_en and name_ru from name based on language."""
    db = SessionLocal()
    
    try:
        logger.info("Updating name_en for EN authors...")
        result1 = db.execute(text("UPDATE authors SET name_en=name WHERE language='en'"))
        db.commit()
        logger.info(f"✅ Updated {result1.rowcount} EN authors (name_en)")
        
        logger.info("Updating name_ru for RU authors...")
        result2 = db.execute(text("UPDATE authors SET name_ru=name WHERE language='ru'"))
        db.commit()
        logger.info(f"✅ Updated {result2.rowcount} RU authors (name_ru)")
        
        # Verify
        en_null = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='en' AND name_en IS NULL")
        ).scalar()
        ru_null = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='ru' AND name_ru IS NULL")
        ).scalar()
        
        logger.info(f"EN authors with NULL name_en: {en_null}")
        logger.info(f"RU authors with NULL name_ru: {ru_null}")
        
        if en_null == 0 and ru_null == 0:
            logger.info("✅ All author name fields updated successfully!")
        else:
            logger.warning(f"⚠️  Some authors still have NULL name fields")
        
    except Exception as e:
        logger.error(f"Error updating author names: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Updating author name_en and name_ru fields")
    logger.info("=" * 60)
    
    update_author_name_fields()
    
    logger.info("=" * 60)
    logger.info("Update complete!")
    logger.info("=" * 60)

