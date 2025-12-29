"""
Translate Russian quotes to English that don't have English translations.

Finds Russian quotes without English translations in the same bilingual_group_id,
translates them using free translation service, and creates English quote records.
"""

import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Quote, QuoteTranslation
from logger_config import setup_logging

# Try to import translation service
try:
    from deep_translator import GoogleTranslator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    print("Warning: deep-translator not available. Install with: pip install deep-translator")

# Setup logging
log_file = Path("logs") / f"translate_ru_to_en_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = setup_logging(log_level="INFO", log_file=str(log_file))


def find_ru_quotes_without_en(db: Session) -> List[Quote]:
    """
    Find Russian quotes that don't have English translations.
    
    A Russian quote doesn't have an English translation if:
    1. It has no bilingual_group_id, OR
    2. It has bilingual_group_id but no English quote in the same group
    
    Args:
        db: Database session
        
    Returns:
        List of Russian quotes without English translations
    """
    try:
        # Get all Russian quotes
        all_ru_quotes = db.query(Quote).filter(Quote.language == 'ru').all()
        
        quotes_without_en = []
        
        for ru_quote in all_ru_quotes:
            has_en_translation = False
            
            if ru_quote.bilingual_group_id:
                # Check if there's an English quote in the same group
                en_quote = db.query(Quote).filter(
                    Quote.bilingual_group_id == ru_quote.bilingual_group_id,
                    Quote.language == 'en'
                ).first()
                
                if en_quote:
                    has_en_translation = True
            
            # Also check QuoteTranslation table
            if not has_en_translation:
                translation = db.query(QuoteTranslation).filter(
                    QuoteTranslation.quote_id == ru_quote.id
                ).join(
                    Quote,
                    QuoteTranslation.translated_quote_id == Quote.id
                ).filter(
                    Quote.language == 'en'
                ).first()
                
                if translation:
                    has_en_translation = True
            
            if not has_en_translation:
                quotes_without_en.append(ru_quote)
        
        logger.info(f"Found {len(quotes_without_en)} Russian quotes without English translations")
        return quotes_without_en
        
    except Exception as e:
        logger.error(f"Error finding Russian quotes without translations: {e}")
        raise


def translate_text(text: str, delay: float = 0.5) -> Optional[str]:
    """
    Translate Russian text to English using Google Translate.
    
    Args:
        text: Russian text to translate
        delay: Delay between requests to avoid rate limiting
        
    Returns:
        Translated English text or None on error
    """
    if not TRANSLATION_AVAILABLE:
        logger.error("Translation service not available")
        return None
    
    if not text or not text.strip():
        return None
    
    try:
        translator = GoogleTranslator(source='ru', target='en')
        translated = translator.translate(text)
        
        # Add delay to avoid rate limiting
        time.sleep(delay)
        
        return translated.strip() if translated else None
        
    except Exception as e:
        logger.error(f"Translation error for '{text[:50]}...': {e}")
        return None


def get_or_create_bilingual_group_id(db: Session, ru_quote: Quote) -> int:
    """
    Get existing bilingual_group_id or create a new one.
    
    Args:
        db: Database session
        ru_quote: Russian quote
        
    Returns:
        bilingual_group_id
    """
    if ru_quote.bilingual_group_id:
        return ru_quote.bilingual_group_id
    
    # Create new group ID
    max_group = db.query(func.max(Quote.bilingual_group_id)).scalar()
    new_group_id = (max_group or 0) + 1
    
    # Assign to Russian quote
    ru_quote.bilingual_group_id = new_group_id
    db.commit()
    
    return new_group_id


def create_english_quote(
    db: Session,
    en_text: str,
    ru_quote: Quote,
    bilingual_group_id: int
) -> Optional[Quote]:
    """
    Create an English quote linked to the Russian quote.
    
    Args:
        db: Database session
        en_text: English translation text
        ru_quote: Russian quote to link to
        bilingual_group_id: Bilingual group ID
        
    Returns:
        Created English quote or None on error
    """
    try:
        # Check if English quote already exists in this group
        existing_en = db.query(Quote).filter(
            Quote.bilingual_group_id == bilingual_group_id,
            Quote.language == 'en'
        ).first()
        
        if existing_en:
            # Update existing English quote if text is different
            if existing_en.text.strip() != en_text.strip():
                logger.info(
                    f"Updating existing English quote ID {existing_en.id} "
                    f"for bilingual_group_id {bilingual_group_id}"
                )
                existing_en.text = en_text.strip()
                db.commit()
                db.refresh(existing_en)
            return existing_en
        
        # Create new English quote
        en_quote = Quote(
            text=en_text.strip(),
            language='en',
            author_id=ru_quote.author_id,  # Copy author from RU quote
            source_id=ru_quote.source_id,  # Copy source from RU quote
            bilingual_group_id=bilingual_group_id
        )
        
        db.add(en_quote)
        db.commit()
        db.refresh(en_quote)
        
        logger.debug(f"Created English quote ID {en_quote.id} for bilingual_group_id {bilingual_group_id}")
        return en_quote
        
    except Exception as e:
        logger.error(f"Error creating English quote: {e}")
        db.rollback()
        return None


def create_translation_link(
    db: Session,
    ru_quote: Quote,
    en_quote: Quote,
    confidence: int = 85  # Lower confidence for auto-translated
) -> bool:
    """
    Create bidirectional translation links between RU and EN quotes.
    
    Args:
        db: Database session
        ru_quote: Russian quote
        en_quote: English quote
        confidence: Confidence score (0-100)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if translation link already exists
        existing = db.query(QuoteTranslation).filter(
            QuoteTranslation.quote_id == ru_quote.id,
            QuoteTranslation.translated_quote_id == en_quote.id
        ).first()
        
        if existing:
            # Update confidence if needed
            if existing.confidence != confidence:
                existing.confidence = confidence
                db.commit()
            return True
        
        # Create RU -> EN translation
        translation_ru_en = QuoteTranslation(
            quote_id=ru_quote.id,
            translated_quote_id=en_quote.id,
            confidence=confidence
        )
        db.add(translation_ru_en)
        
        # Create EN -> RU translation (bidirectional)
        try:
            translation_en_ru = QuoteTranslation(
                quote_id=en_quote.id,
                translated_quote_id=ru_quote.id,
                confidence=confidence
            )
            db.add(translation_en_ru)
        except Exception:
            # May already exist, that's OK
            pass
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error creating translation link: {e}")
        db.rollback()
        return False


def translate_ru_quotes_to_english(limit: Optional[int] = None, delay: float = 0.5):
    """
    Translate Russian quotes without English translations to English.
    
    Args:
        limit: Optional limit on number of quotes to process
        delay: Delay between translation requests (seconds)
    """
    if not TRANSLATION_AVAILABLE:
        logger.error("Translation service not available. Install deep-translator")
        return
    
    logger.info("Starting translation of Russian quotes to English...")
    
    db = SessionLocal()
    
    try:
        # Find Russian quotes without English translations
        ru_quotes = find_ru_quotes_without_en(db)
        
        if not ru_quotes:
            logger.info("No Russian quotes without English translations found")
            return
        
        logger.info(f"Found {len(ru_quotes)} Russian quotes to translate")
        
        if limit:
            ru_quotes = ru_quotes[:limit]
            logger.info(f"Processing first {len(ru_quotes)} quotes (limit applied)")
        
        # Statistics
        stats = {
            'total': len(ru_quotes),
            'success': 0,
            'translation_failed': 0,
            'create_failed': 0,
            'link_failed': 0
        }
        
        # Process each quote
        for idx, ru_quote in enumerate(ru_quotes, 1):
            ru_text = ru_quote.text.strip()
            
            if not ru_text:
                logger.warning(f"Quote ID {ru_quote.id} has empty text, skipping")
                continue
            
            # Translate to English
            logger.debug(f"Translating quote ID {ru_quote.id}: {ru_text[:50]}...")
            en_text = translate_text(ru_text, delay=delay)
            
            if not en_text:
                stats['translation_failed'] += 1
                logger.error(f"Failed to translate quote ID {ru_quote.id}")
                continue
            
            # Get or create bilingual_group_id
            bilingual_group_id = get_or_create_bilingual_group_id(db, ru_quote)
            
            # Create English quote
            en_quote = create_english_quote(db, en_text, ru_quote, bilingual_group_id)
            
            if not en_quote:
                stats['create_failed'] += 1
                logger.error(f"Failed to create English quote for RU quote ID {ru_quote.id}")
                continue
            
            # Create translation links
            if create_translation_link(db, ru_quote, en_quote, confidence=85):
                stats['success'] += 1
                if idx % 10 == 0:
                    logger.info(
                        f"Progress: {idx}/{stats['total']} quotes processed "
                        f"({stats['success']} successful, {stats['translation_failed']} translation failed)"
                    )
            else:
                stats['link_failed'] += 1
                logger.error(f"Failed to create translation link for quote ID {ru_quote.id}")
        
        # Summary
        logger.info("=" * 60)
        logger.info("Translation completed!")
        logger.info(f"Total Russian quotes processed: {stats['total']}")
        logger.info(f"Successfully translated and linked: {stats['success']}")
        logger.info(f"Translation failed: {stats['translation_failed']}")
        logger.info(f"Failed to create EN quote: {stats['create_failed']}")
        logger.info(f"Failed to create link: {stats['link_failed']}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error in translation process: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    limit = None
    delay = 0.5
    
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            logger.warning(f"Invalid limit argument: {sys.argv[1]}")
    
    if len(sys.argv) > 2:
        try:
            delay = float(sys.argv[2])
        except ValueError:
            logger.warning(f"Invalid delay argument: {sys.argv[2]}")
    
    translate_ru_quotes_to_english(limit=limit, delay=delay)

