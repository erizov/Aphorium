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

            logger.info(
                f"Search '{query}' returned {len(results)} bilingual pairs"
            )
            return results

        except Exception as e:
            logger.error(f"Search service error: {e}", exc_info=True)
            # Return empty list instead of raising exception
            # This prevents 500 errors when queries fail
            return []
    
    def _translate_quote_text(self, text: str, target_lang: str) -> Optional[str]:
        """
        Translate quote text word-by-word using translation dictionary.
        
        This is a fallback when translation doesn't exist in database.
        
        Args:
            text: Quote text to translate
            target_lang: Target language ('en' or 'ru')
            
        Returns:
            Translated text or None if translation not possible
        """
        try:
            from utils.translator import translate_query
            
            # Simple word-by-word translation
            words = text.split()
            translated_words = []
            
            for word in words:
                # Clean word (remove punctuation)
                clean_word = ''.join(c for c in word if c.isalnum())
                if not clean_word:
                    translated_words.append(word)
                    continue
                
                # Try to translate
                translation = translate_query(clean_word, self.db)
                if translation and translation.lower() != clean_word.lower():
                    # Replace word with translation, preserving punctuation
                    if word[0].isupper():
                        translation = translation.capitalize()
                    translated_words.append(word.replace(clean_word, translation))
                else:
                    translated_words.append(word)
            
            translated_text = ' '.join(translated_words)
            
            # Only return if we actually translated something
            if translated_text.lower() != text.lower():
                return translated_text
            
            return None
        except Exception as e:
            logger.warning(f"Failed to translate quote text: {e}")
            return None

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
                    "russian": self._quote_to_dict(ru_quote),
                    "is_translated": False,
                    "translation_source": None
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
