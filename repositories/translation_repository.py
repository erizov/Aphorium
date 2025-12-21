"""
Translation repository for managing quote translations.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from models import QuoteTranslation, Quote
from logger_config import logger


class TranslationRepository:
    """Repository for translation operations."""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: Database session
        """
        self.db = db

    def create(
        self,
        quote_id: int,
        translated_quote_id: int,
        confidence: int = 0
    ) -> QuoteTranslation:
        """
        Create a translation link between two quotes.

        Args:
            quote_id: Source quote ID
            translated_quote_id: Translated quote ID
            confidence: Confidence score (0-100)

        Returns:
            Created translation object
        """
        try:
            # Check if translation already exists
            existing = (
                self.db.query(QuoteTranslation)
                .filter(
                    QuoteTranslation.quote_id == quote_id,
                    QuoteTranslation.translated_quote_id == translated_quote_id
                )
                .first()
            )

            if existing:
                logger.debug(
                    f"Translation already exists: {quote_id} -> "
                    f"{translated_quote_id}"
                )
                return existing

            translation = QuoteTranslation(
                quote_id=quote_id,
                translated_quote_id=translated_quote_id,
                confidence=confidence
            )
            self.db.add(translation)
            self.db.commit()
            self.db.refresh(translation)
            logger.debug(
                f"Created translation: {quote_id} -> {translated_quote_id}"
            )
            return translation
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create translation: {e}")
            raise

    def get_by_quote_id(
        self,
        quote_id: int
    ) -> List[QuoteTranslation]:
        """
        Get all translations for a quote.

        Args:
            quote_id: Quote ID

        Returns:
            List of translation objects
        """
        try:
            return (
                self.db.query(QuoteTranslation)
                .filter(QuoteTranslation.quote_id == quote_id)
                .all()
            )
        except Exception as e:
            logger.error(f"Failed to get translations: {e}")
            raise

    def get_translated_quote(
        self,
        quote_id: int,
        target_language: str
    ) -> Optional[Quote]:
        """
        Get the translated quote for a given quote in the target language.
        
        Args:
            quote_id: Source quote ID
            target_language: Target language ('en' or 'ru')
            
        Returns:
            Translated quote or None if not found
        """
        try:
            # Get translations where this quote is the source
            translations = (
                self.db.query(QuoteTranslation)
                .filter(QuoteTranslation.quote_id == quote_id)
                .all()
            )
            
            for trans in translations:
                translated_quote = (
                    self.db.query(Quote)
                    .filter(
                        Quote.id == trans.translated_quote_id,
                        Quote.language == target_language
                    )
                    .first()
                )
                if translated_quote:
                    return translated_quote
            
            # Also check reverse direction (where this quote is the translation)
            reverse_translations = (
                self.db.query(QuoteTranslation)
                .filter(QuoteTranslation.translated_quote_id == quote_id)
                .all()
            )
            
            for trans in reverse_translations:
                source_quote = (
                    self.db.query(Quote)
                    .filter(
                        Quote.id == trans.quote_id,
                        Quote.language == target_language
                    )
                    .first()
                )
                if source_quote:
                    return source_quote
            
            return None
        except Exception as e:
            logger.error(f"Failed to get translated quote: {e}")
            return None

    def get_bilingual_pair(
        self,
        quote_id: int
    ) -> tuple[Optional[Quote], Optional[Quote]]:
        """
        Get bilingual pair (EN and RU) for a quote.
        
        Args:
            quote_id: Quote ID
            
        Returns:
            Tuple of (english_quote, russian_quote)
        """
        try:
            quote = self.db.query(Quote).filter(Quote.id == quote_id).first()
            if not quote:
                return None, None
            
            if quote.language == 'en':
                en_quote = quote
                ru_quote = self.get_translated_quote(quote_id, 'ru')
            else:
                ru_quote = quote
                en_quote = self.get_translated_quote(quote_id, 'en')
            
            return en_quote, ru_quote
        except Exception as e:
            logger.error(f"Failed to get bilingual pair: {e}")
            return None, None
