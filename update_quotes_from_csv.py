"""
Update quotes table from auto_output.csv with Russian translations.

Reads the CSV file, matches English quotes by text, and creates/updates
Russian translations linked via bilingual_group_id.
"""

import csv
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Quote, QuoteTranslation
from logger_config import setup_logging

# Setup logging
log_file = Path("logs") / f"update_quotes_csv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = setup_logging(log_level="INFO", log_file=str(log_file))


def find_quote_by_text(db: Session, text: str, language: str = 'en') -> Optional[Quote]:
    """
    Find a quote by exact text match.
    
    Args:
        db: Database session
        text: Quote text to find
        language: Language code ('en' or 'ru')
        
    Returns:
        Quote object or None if not found
    """
    try:
        # Normalize text for comparison (strip whitespace)
        normalized_text = text.strip()
        
        quote = db.query(Quote).filter(
            Quote.text == normalized_text,
            Quote.language == language
        ).first()
        
        return quote
    except Exception as e:
        logger.error(f"Error finding quote by text: {e}")
        return None


def get_or_create_bilingual_group_id(db: Session, en_quote: Quote) -> int:
    """
    Get existing bilingual_group_id or create a new one.
    
    Args:
        db: Database session
        en_quote: English quote
        
    Returns:
        bilingual_group_id
    """
    if en_quote.bilingual_group_id:
        return en_quote.bilingual_group_id
    
    # Create new group ID
    max_group = db.query(func.max(Quote.bilingual_group_id)).scalar()
    new_group_id = (max_group or 0) + 1
    
    # Assign to English quote
    en_quote.bilingual_group_id = new_group_id
    db.commit()
    
    return new_group_id


def create_russian_quote(
    db: Session,
    ru_text: str,
    en_quote: Quote,
    bilingual_group_id: int
) -> Optional[Quote]:
    """
    Create a Russian quote linked to the English quote.
    
    Args:
        db: Database session
        ru_text: Russian translation text
        en_quote: English quote to link to
        bilingual_group_id: Bilingual group ID
        
    Returns:
        Created Russian quote or None on error
    """
    try:
        # Check if Russian quote already exists in this group
        existing_ru = db.query(Quote).filter(
            Quote.bilingual_group_id == bilingual_group_id,
            Quote.language == 'ru'
        ).first()
        
        if existing_ru:
            # Update existing Russian quote if text is different
            if existing_ru.text.strip() != ru_text.strip():
                logger.info(
                    f"Updating existing Russian quote ID {existing_ru.id} "
                    f"for bilingual_group_id {bilingual_group_id}"
                )
                existing_ru.text = ru_text.strip()
                db.commit()
                db.refresh(existing_ru)
            return existing_ru
        
        # Create new Russian quote
        ru_quote = Quote(
            text=ru_text.strip(),
            language='ru',
            author_id=en_quote.author_id,  # Copy author from EN quote
            source_id=en_quote.source_id,  # Copy source from EN quote
            bilingual_group_id=bilingual_group_id
        )
        
        db.add(ru_quote)
        db.commit()
        db.refresh(ru_quote)
        
        logger.debug(f"Created Russian quote ID {ru_quote.id} for bilingual_group_id {bilingual_group_id}")
        return ru_quote
        
    except Exception as e:
        logger.error(f"Error creating Russian quote: {e}")
        db.rollback()
        return None


def create_translation_link(
    db: Session,
    en_quote: Quote,
    ru_quote: Quote,
    confidence: int = 90
) -> bool:
    """
    Create bidirectional translation links between EN and RU quotes.
    
    Args:
        db: Database session
        en_quote: English quote
        ru_quote: Russian quote
        confidence: Confidence score (0-100)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if translation link already exists
        existing = db.query(QuoteTranslation).filter(
            QuoteTranslation.quote_id == en_quote.id,
            QuoteTranslation.translated_quote_id == ru_quote.id
        ).first()
        
        if existing:
            # Update confidence if needed
            if existing.confidence != confidence:
                existing.confidence = confidence
                db.commit()
            return True
        
        # Create EN -> RU translation
        translation_en_ru = QuoteTranslation(
            quote_id=en_quote.id,
            translated_quote_id=ru_quote.id,
            confidence=confidence
        )
        db.add(translation_en_ru)
        
        # Create RU -> EN translation (bidirectional)
        try:
            translation_ru_en = QuoteTranslation(
                quote_id=ru_quote.id,
                translated_quote_id=en_quote.id,
                confidence=confidence
            )
            db.add(translation_ru_en)
        except Exception:
            # May already exist, that's OK
            pass
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error creating translation link: {e}")
        db.rollback()
        return False


def process_csv_row(
    db: Session,
    row: dict,
    stats: dict
) -> Tuple[bool, str]:
    """
    Process a single CSV row and update database.
    
    Args:
        db: Database session
        row: CSV row dictionary
        stats: Statistics dictionary to update
        
    Returns:
        Tuple of (success, message)
    """
    en_text = row.get('Original_Text', '').strip()
    ru_text = row.get('Translated_Text', '').strip()
    detected_lang = row.get('Detected_Lang', '').lower()
    
    if not en_text or not ru_text:
        stats['skipped_empty'] += 1
        return False, "Empty text"
    
    if detected_lang != 'en':
        stats['skipped_not_en'] += 1
        return False, f"Not English (detected: {detected_lang})"
    
    # Find English quote
    en_quote = find_quote_by_text(db, en_text, language='en')
    
    if not en_quote:
        stats['not_found'] += 1
        return False, f"English quote not found in database"
    
    # Get or create bilingual_group_id
    bilingual_group_id = get_or_create_bilingual_group_id(db, en_quote)
    
    # Create or update Russian quote
    ru_quote = create_russian_quote(db, ru_text, en_quote, bilingual_group_id)
    
    if not ru_quote:
        stats['create_failed'] += 1
        return False, "Failed to create Russian quote"
    
    # Create translation links
    if create_translation_link(db, en_quote, ru_quote, confidence=90):
        stats['success'] += 1
        return True, f"Linked quotes EN={en_quote.id} RU={ru_quote.id} group={bilingual_group_id}"
    else:
        stats['link_failed'] += 1
        return False, "Failed to create translation link"


def update_quotes_from_csv(csv_file: str = 'auto_output.csv'):
    """
    Update quotes table from CSV file.
    
    Args:
        csv_file: Path to CSV file
    """
    csv_path = Path(csv_file)
    
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_file}")
        return
    
    logger.info(f"Reading CSV file: {csv_file}")
    
    # Statistics
    stats = {
        'total': 0,
        'success': 0,
        'not_found': 0,
        'skipped_empty': 0,
        'skipped_not_en': 0,
        'create_failed': 0,
        'link_failed': 0
    }
    
    db = SessionLocal()
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for idx, row in enumerate(reader, 1):
                stats['total'] += 1
                
                success, message = process_csv_row(db, row, stats)
                
                if idx % 100 == 0:
                    logger.info(
                        f"Processed {idx} rows: "
                        f"{stats['success']} successful, "
                        f"{stats['not_found']} not found, "
                        f"{stats['skipped_empty'] + stats['skipped_not_en']} skipped"
                    )
                
                if not success and idx <= 10:  # Log first 10 failures for debugging
                    logger.debug(f"Row {idx}: {message}")
        
        # Summary
        logger.info("=" * 60)
        logger.info("Update completed!")
        logger.info(f"Total rows processed: {stats['total']}")
        logger.info(f"Successfully linked: {stats['success']}")
        logger.info(f"English quotes not found: {stats['not_found']}")
        logger.info(f"Skipped (empty): {stats['skipped_empty']}")
        logger.info(f"Skipped (not EN): {stats['skipped_not_en']}")
        logger.info(f"Failed to create RU quote: {stats['create_failed']}")
        logger.info(f"Failed to create link: {stats['link_failed']}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error processing CSV: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    csv_file = 'auto_output.csv'
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    update_quotes_from_csv(csv_file)

