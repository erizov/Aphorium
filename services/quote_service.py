"""
Quote service for business logic operations.
"""

from typing import Optional
from sqlalchemy.orm import Session

from repositories.quote_repository import QuoteRepository
from repositories.translation_repository import TranslationRepository
from models import Quote
from logger_config import logger


class QuoteService:
    """Service for quote operations."""

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: Database session
        """
        self.quote_repo = QuoteRepository(db)
        self.translation_repo = TranslationRepository(db)

    def get_quote_with_translations(self, quote_id: int) -> Optional[dict]:
        """
        Get quote with its translations.

        Args:
            quote_id: Quote ID

        Returns:
            Quote dictionary with translations or None
        """
        try:
            quote, translations = self.quote_repo.get_with_translations(
                quote_id
            )

            if not quote:
                return None

            result = {
                "id": quote.id,
                "text": quote.text,
                "language": quote.language,
                "author": {
                    "id": quote.author.id,
                    "name": (
                        quote.author.name_en if quote.language == 'en' 
                        else quote.author.name_ru
                    ) if quote.author else None,
                    "name_en": quote.author.name_en if quote.author else None,
                    "name_ru": quote.author.name_ru if quote.author else None,
                    "bio": quote.author.bio if quote.author else None
                } if quote.author else None,
                "source": {
                    "id": quote.source.id,
                    "title": quote.source.title
                } if quote.source else None,
                "translations": [
                    {
                        "id": t.id,
                        "text": t.text,
                        "language": t.language,
                        "author": {
                            "id": t.author.id,
                            "name": (
                                t.author.name_en if t.language == 'en' 
                                else t.author.name_ru
                            ) if t.author else None,
                            "name_en": t.author.name_en if t.author else None,
                            "name_ru": t.author.name_ru if t.author else None,
                            "bio": t.author.bio if t.author else None
                        } if t.author else None
                    }
                    for t in translations
                ]
            }

            return result
        except Exception as e:
            logger.error(f"Failed to get quote with translations: {e}")
            raise

