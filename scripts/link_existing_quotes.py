"""
Script to link existing quotes by author and create bilingual groups.

This will:
1. Find authors with quotes in both EN and RU
2. Match quotes by author + source + similarity
3. Create bilingual_group_id assignments
4. Create QuoteTranslation records
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from services.bilingual_linker import BilingualLinker
from logger_config import logger


def main():
    """Link existing quotes."""
    db = SessionLocal()
    linker = BilingualLinker(db)
    
    try:
        logger.info("=" * 60)
        logger.info("Linking Existing Quotes")
        logger.info("=" * 60)
        
        # Step 1: Populate group IDs from existing translations
        logger.info("\nStep 1: Populating bilingual_group_id from existing translations...")
        groups_created = linker.populate_group_ids_from_translations()
        logger.info(f"✅ Created {groups_created} bilingual groups from existing translations")
        
        # Step 2: Link quotes by author
        logger.info("\nStep 2: Linking quotes by author...")
        links_created = linker.link_all_bilingual_authors()
        logger.info(f"✅ Created {links_created} additional links")
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Summary:")
        logger.info(f"  Groups created: {groups_created}")
        logger.info(f"  Links created: {links_created}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Failed to link quotes: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

