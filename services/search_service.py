"""
Search service for quotes.

Handles search logic with bilingual preference and ranking.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from repositories.quote_repository import QuoteRepository
from repositories.translation_repository import TranslationRepository
from models import Quote
from utils.translator import get_bilingual_search_queries
from logger_config import logger


class SearchService:
    """Service for quote search operations."""

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: Database session
        """
        self.db = db
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
        Search quotes and return as bilingual pairs (EN + RU side by side).
        
        For each quote found, returns both English and Russian versions if available.
        If translation doesn't exist in database, attempts word-by-word translation
        and notes it in the result.

        Args:
            query: Search query text
            language: Filter by language ('en', 'ru', 'both', or None)
            prefer_bilingual: Prioritize quotes with translations in database
            limit: Maximum number of quote pairs

        Returns:
            List of bilingual pair dictionaries: [{"english": {...}, "russian": {...}}, ...]
        """
        try:
            # Determine language filter
            lang_filter = None
            if language and language != "both":
                lang_filter = language

            # Search for quotes matching the query
            # Don't translate the query - search for quotes that exist
            search_limit = limit * 2  # Get more quotes to find pairs
            quotes = self.quote_repo.search(
                query=query,
                language=lang_filter,
                limit=search_limit
            )
            
            # Build bilingual pairs
            results = []
            seen_pairs = set()  # Track pairs we've already added
            
            for quote in quotes:
                # Get bilingual pair for this quote
                en_quote, ru_quote = self.translation_repo.get_bilingual_pair(quote.id)
                
                # Create pair key to avoid duplicates
                if en_quote and ru_quote:
                    pair_key = (en_quote.id, ru_quote.id)
                elif en_quote:
                    pair_key = (en_quote.id, None)
                elif ru_quote:
                    pair_key = (None, ru_quote.id)
                else:
                    # No translation found - use original quote
                    if quote.language == 'en':
                        pair_key = (quote.id, None)
                    else:
                        pair_key = (None, quote.id)
                
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                
                # Build pair dictionary
                pair_dict = {
                    "english": None,
                    "russian": None,
                    "is_translated": False,
                    "translation_source": None
                }
                
                if en_quote:
                    pair_dict["english"] = self._quote_to_dict(en_quote)
                elif quote.language == 'en':
                    pair_dict["english"] = self._quote_to_dict(quote)
                
                if ru_quote:
                    pair_dict["russian"] = self._quote_to_dict(ru_quote)
                elif quote.language == 'ru':
                    pair_dict["russian"] = self._quote_to_dict(quote)
                
                # If we have one language but not the other, try word-by-word translation
                if pair_dict["english"] and not pair_dict["russian"]:
                    # Try to translate English quote to Russian
                    translated_text = self._translate_quote_text(
                        pair_dict["english"]["text"],
                        target_lang="ru"
                    )
                    if translated_text and translated_text != pair_dict["english"]["text"]:
                        pair_dict["russian"] = {
                            "id": None,  # Not in database
                            "text": translated_text,
                            "language": "ru",
                            "author": pair_dict["english"]["author"],
                            "source": pair_dict["english"]["source"],
                            "has_translation": False,
                            "translation_count": 0,
                            "created_at": None
                        }
                        pair_dict["is_translated"] = True
                        pair_dict["translation_source"] = "word_translation_dict"
                
                elif pair_dict["russian"] and not pair_dict["english"]:
                    # Try to translate Russian quote to English
                    translated_text = self._translate_quote_text(
                        pair_dict["russian"]["text"],
                        target_lang="en"
                    )
                    if translated_text and translated_text != pair_dict["russian"]["text"]:
                        pair_dict["english"] = {
                            "id": None,  # Not in database
                            "text": translated_text,
                            "language": "en",
                            "author": pair_dict["russian"]["author"],
                            "source": pair_dict["russian"]["source"],
                            "has_translation": False,
                            "translation_count": 0,
                            "created_at": None
                        }
                        pair_dict["is_translated"] = True
                        pair_dict["translation_source"] = "word_translation_dict"
                
                # Only add pairs that have at least one language
                if pair_dict["english"] or pair_dict["russian"]:
                    results.append(pair_dict)
                
                if len(results) >= limit:
                    break

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
                    
                    # Alternate between languages to ensure both are represented
                    en_idx = 0
                    ru_idx = 0
                    while len(results) < limit and (en_idx < len(en_matched) or ru_idx < len(ru_matched)):
                        # Add Russian quote if available and we need more Russian results
                        ru_count = len([r for r in results if r['language'] == 'ru'])
                        if ru_idx < len(ru_matched) and (ru_count < target_per_lang or en_idx >= len(en_matched)):
                            quote = ru_matched[ru_idx]
                            if quote not in results:
                                results.append(quote)
                            ru_idx += 1
                        # Add English quote if available
                        elif en_idx < len(en_matched):
                            quote = en_matched[en_idx]
                            if quote not in results:
                                results.append(quote)
                            en_idx += 1
                        else:
                            break
                
                # Step 3: Ensure both languages are represented
                # Count languages in current results
                en_count = len([r for r in results if r['language'] == 'en'])
                ru_count = len([r for r in results if r['language'] == 'ru'])
                
                # If we have results but missing one language, add some from missing language
                # This should happen even if we've hit the limit - we'll replace some results
                if len(results) > 0:
                    if ru_count == 0:
                        # No Russian quotes - add some, even if we need to remove some English ones
                        ru_quotes_models = self.db.query(Quote).filter(
                            Quote.language == 'ru'
                        ).order_by(func.random()).limit(min(5, max(3, limit // 3))).all()
                        
                        # Remove some English quotes to make room for Russian ones
                        # Keep at least half English if possible
                        en_to_remove = min(len(ru_quotes_models), en_count // 2) if en_count > 3 else 0
                        if en_to_remove > 0:
                            # Remove English quotes from the end (keep the best matches)
                            results = [r for r in results if r['language'] != 'en'][:limit - en_to_remove]
                            # Add back some English quotes
                            en_kept = [r for r in en_quotes if r not in results][:en_to_remove]
                            results = en_kept + results
                        
                        # Add Russian quotes
                        for quote in ru_quotes_models:
                            if len(results) >= limit:
                                break
                            quote_dict = self._quote_to_dict(quote)
                            quote_dict["has_translation"] = False
                            quote_dict["translation_count"] = 0
                            if not any(r['id'] == quote_dict['id'] for r in results):
                                results.append(quote_dict)
                        
                        # Trim to limit if we exceeded it
                        results = results[:limit]
                        
                    elif en_count == 0:
                        # No English quotes - add some, even if we need to remove some Russian ones
                        en_quotes_models = self.db.query(Quote).filter(
                            Quote.language == 'en'
                        ).order_by(func.random()).limit(min(5, max(3, limit // 3))).all()
                        
                        # Remove some Russian quotes to make room for English ones
                        ru_to_remove = min(len(en_quotes_models), ru_count // 2) if ru_count > 3 else 0
                        if ru_to_remove > 0:
                            # Remove Russian quotes from the end
                            results = [r for r in results if r['language'] != 'ru'][:limit - ru_to_remove]
                            # Add back some Russian quotes
                            ru_kept = [r for r in ru_quotes if r not in results][:ru_to_remove]
                            results = ru_kept + results
                        
                        # Add English quotes
                        for quote in en_quotes_models:
                            if len(results) >= limit:
                                break
                            quote_dict = self._quote_to_dict(quote)
                            quote_dict["has_translation"] = False
                            quote_dict["translation_count"] = 0
                            if not any(r['id'] == quote_dict['id'] for r in results):
                                results.append(quote_dict)
                        
                        # Trim to limit if we exceeded it
                        results = results[:limit]
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
            logger.error(f"Search service error: {e}", exc_info=True)
            # Return empty list instead of raising exception
            # This prevents 500 errors when queries fail
            return []

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

