"""
Search service for quotes.

Handles search logic with bilingual preference and ranking.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from repositories.quote_repository import QuoteRepository
from repositories.translation_repository import TranslationRepository
from models import Quote
from logger_config import logger


class SearchService:
    """Service for quote search operations."""

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: Database session
        """
        self.quote_repo = QuoteRepository(db)
        self.translation_repo = TranslationRepository(db)

    def search(
        self,
        query: str,
        language: Optional[str] = None,
        prefer_bilingual: bool = True,
        limit: int = 50
    ) -> List[dict]:
        """
        Search quotes with bilingual preference.

        Args:
            query: Search query text
            language: Filter by language ('en', 'ru', 'both', or None)
            prefer_bilingual: Prioritize quotes with translations
            limit: Maximum number of results

        Returns:
            List of quote dictionaries with metadata
        """
        try:
            # Determine language filter
            lang_filter = None
            if language and language != "both":
                lang_filter = language

            # Perform search
            quotes = self.quote_repo.search(
                query=query,
                language=lang_filter,
                limit=limit * 2 if prefer_bilingual else limit
            )

            # Enrich with translation info
            results = []
            bilingual_quotes = []
            regular_quotes = []

            for quote in quotes:
                quote_dict = self._quote_to_dict(quote)

                # Check if quote has translations
                translations = self.translation_repo.get_by_quote_id(quote.id)
                if translations:
                    quote_dict["has_translation"] = True
                    quote_dict["translation_count"] = len(translations)
                    bilingual_quotes.append(quote_dict)
                else:
                    quote_dict["has_translation"] = False
                    quote_dict["translation_count"] = 0
                    regular_quotes.append(quote_dict)

            # Prioritize bilingual quotes if requested
            if prefer_bilingual:
                results = bilingual_quotes + regular_quotes
            else:
                results = bilingual_quotes + regular_quotes

            # Limit results
            results = results[:limit]

            logger.info(
                f"Search '{query}' returned {len(results)} results "
                f"({len(bilingual_quotes)} bilingual)"
            )
            return results

        except Exception as e:
            logger.error(f"Search service error: {e}")
            raise

    def get_bilingual_pairs(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[dict]:
        """
        Get quotes with both English and Russian versions.

        Args:
            limit: Maximum number of pairs
            offset: Result offset for pagination

        Returns:
            List of bilingual pair dictionaries
        """
        try:
            pairs = self.quote_repo.get_bilingual_pairs(limit, offset)
            results = []

            for en_quote, ru_quote in pairs:
                results.append({
                    "english": self._quote_to_dict(en_quote),
                    "russian": self._quote_to_dict(ru_quote)
                })

            return results
        except Exception as e:
            logger.error(f"Failed to get bilingual pairs: {e}")
            raise

    def _quote_to_dict(self, quote: Quote) -> dict:
        """
        Convert quote model to dictionary.

        Args:
            quote: Quote model instance

        Returns:
            Quote dictionary compatible with QuoteSchema
        """
        result = {
            "id": quote.id,
            "text": quote.text,
            "language": quote.language,
            "author": None,
            "source": None,
            "created_at": quote.created_at.isoformat() if quote.created_at
            else None
        }
        
        # Add author if exists
        if quote.author:
            result["author"] = {
                "id": quote.author.id,
                "name": quote.author.name,
                "language": quote.author.language,
                "bio": quote.author.bio
            }
        
        # Add source if exists
        if quote.source:
            result["source"] = {
                "id": quote.source.id,
                "title": quote.source.title,
                "language": quote.source.language,
                "source_type": quote.source.source_type
            }
        
        return result

