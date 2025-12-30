"""
Verify and update ALL author name_en and name_ru fields (no ID restrictions).

This script:
1. Checks current state of all authors
2. Updates ALL records (not just ID >= 186)
3. Verifies all records are updated
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from sqlalchemy import text
from logger_config import logger


def verify_and_update_all_authors():
    """Verify and update ALL author name fields."""
    db = SessionLocal()
    
    try:
        # Check current state
        total_en = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='en'")
        ).scalar()
        total_ru = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='ru'")
        ).scalar()
        
        en_with_name_en = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='en' AND name_en IS NOT NULL")
        ).scalar()
        ru_with_name_ru = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='ru' AND name_ru IS NOT NULL")
        ).scalar()
        
        en_null = total_en - en_with_name_en
        ru_null = total_ru - ru_with_name_ru
        
        logger.info("=" * 60)
        logger.info("Current State:")
        logger.info(f"  Total EN authors: {total_en}")
        logger.info(f"  EN authors with name_en: {en_with_name_en}")
        logger.info(f"  EN authors with NULL name_en: {en_null}")
        logger.info(f"  Total RU authors: {total_ru}")
        logger.info(f"  RU authors with name_ru: {ru_with_name_ru}")
        logger.info(f"  RU authors with NULL name_ru: {ru_null}")
        logger.info("=" * 60)
        
        # Update ALL records (no ID restriction)
        logger.info("Updating name_en for ALL EN authors...")
        result1 = db.execute(text("UPDATE authors SET name_en=name WHERE language='en'"))
        db.commit()
        logger.info(f"✅ Updated {result1.rowcount} EN authors (name_en)")
        
        logger.info("Updating name_ru for ALL RU authors...")
        result2 = db.execute(text("UPDATE authors SET name_ru=name WHERE language='ru'"))
        db.commit()
        logger.info(f"✅ Updated {result2.rowcount} RU authors (name_ru)")
        
        # Verify final state
        final_en_null = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='en' AND name_en IS NULL")
        ).scalar()
        final_ru_null = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='ru' AND name_ru IS NULL")
        ).scalar()
        
        final_en_with_name = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='en' AND name_en IS NOT NULL")
        ).scalar()
        final_ru_with_name = db.execute(
            text("SELECT COUNT(*) FROM authors WHERE language='ru' AND name_ru IS NOT NULL")
        ).scalar()
        
        logger.info("=" * 60)
        logger.info("Final State:")
        logger.info(f"  EN authors with name_en: {final_en_with_name} / {total_en}")
        logger.info(f"  EN authors with NULL name_en: {final_en_null}")
        logger.info(f"  RU authors with name_ru: {final_ru_with_name} / {total_ru}")
        logger.info(f"  RU authors with NULL name_ru: {final_ru_null}")
        logger.info("=" * 60)
        
        if final_en_null == 0 and final_ru_null == 0:
            logger.info("✅ All author name fields updated successfully!")
        else:
            logger.warning(f"⚠️  Some authors still have NULL name fields")
        
        # Show some examples
        logger.info("\nSample records:")
        sample_en = db.execute(
            text("SELECT id, name, name_en, language FROM authors WHERE language='en' LIMIT 5")
        ).fetchall()
        for row in sample_en:
            logger.info(f"  ID {row[0]}: name='{row[1]}', name_en='{row[2]}', lang={row[3]}")
        
        sample_ru = db.execute(
            text("SELECT id, name, name_ru, language FROM authors WHERE language='ru' LIMIT 5")
        ).fetchall()
        for row in sample_ru:
            logger.info(f"  ID {row[0]}: name='{row[1]}', name_ru='{row[2]}', lang={row[3]}")
        
    except Exception as e:
        logger.error(f"Error updating author names: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Verifying and updating ALL author name_en and name_ru fields")
    logger.info("(No ID restrictions - updating entire table)")
    logger.info("=" * 60)
    
    verify_and_update_all_authors()
    
    logger.info("=" * 60)
    logger.info("Update complete!")
    logger.info("=" * 60)

