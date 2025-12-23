"""
Script to populate bilingual_group_id for existing quotes.

Scans existing QuoteTranslation records and assigns bilingual_group_id
to enable fast bilingual pair retrieval.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from services.bilingual_linker import BilingualLinker
from logger_config import logger


def main():
    """Populate bilingual groups from existing translations."""
    db = SessionLocal()
    linker = BilingualLinker(db)
    
    try:
        logger.info("Populating bilingual_group_id from existing translations...")
        groups_created = linker.populate_group_ids_from_translations()
        logger.info(f"✅ Created {groups_created} bilingual groups")
        
        # Also try to link remaining quotes
        logger.info("Linking remaining quotes by author...")
        links_created = linker.link_all_bilingual_authors()
        logger.info(f"✅ Created {links_created} additional links")
        
    except Exception as e:
        logger.error(f"Failed to populate groups: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

