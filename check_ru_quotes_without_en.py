"""
Check how many Russian quotes don't have English translations.
"""

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Quote, QuoteTranslation
from logger_config import logger


def check_ru_quotes_without_en():
    """Check and report Russian quotes without English translations."""
    db = SessionLocal()
    
    try:
        # Get all Russian quotes
        all_ru_quotes = db.query(Quote).filter(Quote.language == 'ru').all()
        
        quotes_without_en = []
        quotes_with_en = []
        
        for ru_quote in all_ru_quotes:
            has_en_translation = False
            
            # Check bilingual_group_id
            if ru_quote.bilingual_group_id:
                en_quote = db.query(Quote).filter(
                    Quote.bilingual_group_id == ru_quote.bilingual_group_id,
                    Quote.language == 'en'
                ).first()
                
                if en_quote:
                    has_en_translation = True
            
            # Check QuoteTranslation table
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
            
            if has_en_translation:
                quotes_with_en.append(ru_quote)
            else:
                quotes_without_en.append(ru_quote)
        
        print("=" * 60)
        print("Russian Quotes Translation Status")
        print("=" * 60)
        print(f"Total Russian quotes: {len(all_ru_quotes)}")
        print(f"Quotes WITH English translation: {len(quotes_with_en)}")
        print(f"Quotes WITHOUT English translation: {len(quotes_without_en)}")
        print("=" * 60)
        
        if quotes_without_en:
            print(f"\nFirst 10 Russian quotes without English translations:")
            for i, quote in enumerate(quotes_without_en[:10], 1):
                print(f"{i}. ID {quote.id}: {quote.text[:80]}...")
        
        return len(quotes_without_en)
        
    except Exception as e:
        logger.error(f"Error checking quotes: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    check_ru_quotes_without_en()

