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
                # Strategy: Get bilingual quotes first, then mix EN and RU quotes
                
                # Step 1: Add bilingual quotes (these are in both languages)
                for quote in bilingual_quotes:
                    if len(results) >= limit:
                        break
                    if quote not in results:
                        results.append(quote)
                
                # Step 2: If we don't have enough results, add from both languages
                # Try to get a balanced mix
                en_matched = [q for q in en_quotes if q not in results]
                ru_matched = [q for q in ru_quotes if q not in results]
                
                # Calculate how many from each language we should add
                remaining = limit - len(results)
                if remaining > 0:
                    # Try to get roughly equal numbers from each language
                    # But if one language has fewer matches, use what's available
                    target_per_lang = max(1, remaining // 2)
                    
                    # Add Russian quotes first (since we have fewer of them)
                    for quote in ru_matched[:target_per_lang]:
                        if len(results) >= limit:
                            break
                        if quote not in results:
                            results.append(quote)
                    
                    # Then add English quotes
                    for quote in en_matched[:remaining]:
                        if len(results) >= limit:
                            break
                        if quote not in results:
                            results.append(quote)
                
                # Step 3: If we still don't have Russian results and have room,
                # add some Russian quotes to ensure bilingual results
                ru_count = len([r for r in results if r['language'] == 'ru'])
                if ru_count == 0 and len(results) < limit:
                    # Get some random Russian quotes to show variety
                    ru_quotes_models = self.db.query(Quote).filter(
                        Quote.language == 'ru'
                    ).order_by(func.random()).limit(
                        min(3, limit - len(results))
                    ).all()
                    
                    for quote in ru_quotes_models:
                        if len(results) >= limit:
                            break
                        quote_dict = self._quote_to_dict(quote)
                        quote_dict["has_translation"] = False
                        quote_dict["translation_count"] = 0
                        # Check if already in results by ID
                        if not any(r['id'] == quote_dict['id'] for r in results):
                            results.append(quote_dict)
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

