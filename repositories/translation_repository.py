"""
Translation repository for managing quote translations.
"""

from typing import Optional
from sqlalchemy.orm import Session

from models import QuoteTranslation
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
    ) -> list[QuoteTranslation]:
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

