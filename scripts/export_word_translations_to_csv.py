"""
Export existing word_translations to CSV backup file.

Creates CSV backup of all existing word translations without deleting them.
"""

import sys
import csv
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import WordTranslation
from logger_config import logger

CSV_BACKUP_FILE = "data/word_translations_backup.csv"


def export_to_csv() -> int:
    """
    Export all word translations to CSV.
    
    Returns:
        Number of records exported
    """
    db = SessionLocal()
    
    try:
        # Get all word translations
        translations = db.query(WordTranslation).order_by(WordTranslation.id).all()
        
        if not translations:
            logger.info("No word translations found in database")
            return 0
        
        logger.info(f"Found {len(translations)} word translations to export")
        
        # Create data directory if needed
        Path("data").mkdir(exist_ok=True)
        
        # Write to CSV
        with open(CSV_BACKUP_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['word_en', 'word_ru'])
            writer.writeheader()
            
            for trans in translations:
                writer.writerow({
                    'word_en': trans.word_en,
                    'word_ru': trans.word_ru
                })
        
        logger.info(f"Exported {len(translations)} word translations to {CSV_BACKUP_FILE}")
        return len(translations)
    
    except Exception as e:
        logger.error(f"Failed to export word translations: {e}", exc_info=True)
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Exporting word translations to CSV backup")
    logger.info("=" * 60)
    
    count = export_to_csv()
    
    logger.info("=" * 60)
    logger.info(f"Export complete: {count} records saved to {CSV_BACKUP_FILE}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

