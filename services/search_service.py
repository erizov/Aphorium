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
        
        Always returns results from both languages unless explicitly filtered.
        Ensures a balanced mix of English and Russian quotes.

        Args:
            query: Search query text
            language: Filter by language ('en', 'ru', 'both', or None)
            prefer_bilingual: Prioritize quotes with translations
            limit: Maximum number of results

        Returns:
            List of quote dictionaries with metadata from both languages
        """
        try:
            # Determine language filter
            lang_filter = None
            if language and language != "both":
                lang_filter = language

            # Search with higher limit to get results from both languages
            search_limit = limit * 3 if not lang_filter else limit * 2
            quotes = self.quote_repo.search(
                query=query,
                language=lang_filter,
                limit=search_limit
            )

            # Enrich with translation info and separate by language
            en_quotes = []
            ru_quotes = []
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
                
                # Separate by language for balanced results
                if quote.language == "en":
                    en_quotes.append(quote_dict)
                elif quote.language == "ru":
                    ru_quotes.append(quote_dict)

            # Build results ensuring both languages are represented
            results = []
            
            if not lang_filter:
                # When searching both languages, ensure we get results from both
                # Take bilingual quotes first, then alternate between languages
                bilingual_added = 0
                en_added = 0
                ru_added = 0
                max_per_lang = limit // 2  # Try to get roughly half from each language
                
                # Add bilingual quotes first
                for quote in bilingual_quotes:
                    if len(results) >= limit:
                        break
                    results.append(quote)
                    bilingual_added += 1
                
                # Then add regular quotes, alternating between languages
                en_idx = 0
                ru_idx = 0
                while len(results) < limit and (en_idx < len(en_quotes) or ru_idx < len(ru_quotes)):
                    # Alternate between languages, but respect max_per_lang
                    if ru_idx < len(ru_quotes) and ru_added < max_per_lang:
                        # Add Russian quote
                        if ru_quotes[ru_idx] not in results:
                            results.append(ru_quotes[ru_idx])
                            ru_added += 1
                        ru_idx += 1
                    elif en_idx < len(en_quotes) and en_added < max_per_lang:
                        # Add English quote
                        if en_quotes[en_idx] not in results:
                            results.append(en_quotes[en_idx])
                            en_added += 1
                        en_idx += 1
                    else:
                        # If we've hit max for one language, add from the other
                        if ru_idx < len(ru_quotes) and ru_quotes[ru_idx] not in results:
                            results.append(ru_quotes[ru_idx])
                            ru_idx += 1
                        elif en_idx < len(en_quotes) and en_quotes[en_idx] not in results:
                            results.append(en_quotes[en_idx])
                            en_idx += 1
                        else:
                            break
            else:
                # Language filter specified - use original logic
                if prefer_bilingual:
                    results = bilingual_quotes + regular_quotes
                else:
                    results = bilingual_quotes + regular_quotes
                results = results[:limit]

            logger.info(
                f"Search '{query}' returned {len(results)} results "
                f"(EN: {len([r for r in results if r['language'] == 'en'])}, "
                f"RU: {len([r for r in results if r['language'] == 'ru'])}, "
                f"bilingual: {len(bilingual_quotes)})"
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

