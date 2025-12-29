"""
Search service for quotes.

Handles search logic with bilingual preference and ranking.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from repositories.quote_repository import QuoteRepository
from repositories.translation_repository import TranslationRepository
from services.bilingual_pair_builder import BilingualPairBuilder
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
        self.pair_builder = BilingualPairBuilder(db)

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
            # Get more quotes to find pairs
            search_limit = limit * 2
            quotes = self.quote_repo.search(
                query=query,
                language=lang_filter,
                limit=search_limit
            )
            
            # Use BilingualPairBuilder to build pairs (simplified approach)
            results = self.pair_builder.build_pairs(quotes, prefer_bilingual)
            
            # Limit results
            results = results[:limit]

            logger.info(
                f"Search '{query}' returned {len(results)} bilingual pairs"
            )
            return results

        except Exception as e:
            logger.error(f"Search service error: {e}", exc_info=True)
            # Return empty list instead of raising exception
            # This prevents 500 errors when queries fail
            return []
    
    def _find_matching_quote_by_author(
        self,
        author_name: Optional[str],
        target_language: str,
        source_id: Optional[int] = None,
        source_text: Optional[str] = None
    ) -> Optional[Quote]:
        """
        Find a quote from the same author in the target language.
        
        Uses text similarity matching: if 4+ words match, considers it an exact match.
        
        Args:
            author_name: Name of the author to match
            target_language: Target language ('en' or 'ru')
            source_id: Optional source ID to match (if available)
            source_text: Optional source quote text for similarity matching
            
        Returns:
            Matching quote or None if not found
        """
        if not author_name:
            return None
        
        try:
            from models import Author
            
            # Find author in target language by name
            author = (
                self.db.query(Author)
                .filter(
                    Author.name == author_name,
                    Author.language == target_language
                )
                .first()
            )
            
            if not author:
                return None
            
            # Get all quotes from this author in target language
            quotes = (
                self.db.query(Quote)
                .filter(
                    Quote.author_id == author.id,
                    Quote.language == target_language
                )
                .all()
            )
            
            if not quotes:
                return None
            
            # If we have source text, do similarity matching
            if source_text:
                source_words = set(
                    word.lower().strip('.,!?;:()[]{}"\'')
                    for word in source_text.split()
                    if len(word.strip('.,!?;:()[]{}"\'')) > 0
                )
                
                best_match = None
                best_match_count = 0
                
                for quote in quotes:
                    quote_words = set(
                        word.lower().strip('.,!?;:()[]{}"\'')
                        for word in quote.text.split()
                        if len(word.strip('.,!?;:()[]{}"\'')) > 0
                    )
                    
                    # Count matching words
                    matching_words = source_words & quote_words
                    match_count = len(matching_words)
                    
                    # If 4+ words match, consider it an exact match
                    if match_count >= 4:
                        # Prefer quotes from same source if available
                        if source_id and quote.source_id == source_id:
                            return quote
                        # Track best match
                        if match_count > best_match_count:
                            best_match = quote
                            best_match_count = match_count
                
                # Return best match if we found one with 4+ words
                if best_match_count >= 4:
                    return best_match
            
            # Fallback: if source_id provided, prefer quotes from same source
            # But only if we have text similarity (already checked above)
            if source_id and best_match and best_match.source_id == source_id:
                return best_match
            
            # Only return best match if we found one with 4+ words
            # Do NOT return first quote from author - that's not a translation!
            return best_match
            
        except Exception as e:
            logger.warning(f"Failed to find matching quote by author: {e}")
            return None
    
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
            from repositories.translation_word_repository import TranslationWordRepository
            from utils.text_utils import detect_language
            
            repo = TranslationWordRepository(self.db)
            
            # Simple word-by-word translation
            words = text.split()
            translated_words = []
            translated_count = 0
            
            for word in words:
                # Clean word (remove punctuation)
                clean_word = ''.join(c for c in word if c.isalnum())
                if not clean_word:
                    translated_words.append(word)
                    continue
                
                # Detect source language
                source_lang = detect_language(clean_word)
                if source_lang == 'unknown':
                    # Default to opposite of target
                    source_lang = 'en' if target_lang == 'ru' else 'ru'
                
                # Try to translate using repository
                translation = repo.get_translation(clean_word.lower())
                
                if translation and translation.lower() != clean_word.lower():
                    # Replace word with translation, preserving punctuation
                    if word[0].isupper():
                        translation = translation.capitalize()
                    translated_words.append(word.replace(clean_word, translation))
                    translated_count += 1
                else:
                    translated_words.append(word)
            
            translated_text = ' '.join(translated_words)
            
            # Only return if we actually translated something
            if translated_count > 0 and translated_text.lower() != text.lower():
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
            "has_translation": None,
            "translation_count": None,
            "created_at": quote.created_at.isoformat() if quote.created_at
            else None
        }
        
        # Add author if exists (matching AuthorSchema)
        if quote.author:
            result["author"] = {
                "id": quote.author.id,
                "name": quote.author.name,
                "language": quote.author.language,
                "bio": quote.author.bio
            }
        
        # Add source if exists (matching SourceSchema)
        if quote.source:
            result["source"] = {
                "id": quote.source.id,
                "title": quote.source.title,
                "language": quote.source.language,
                "source_type": quote.source.source_type
            }
        
        return result
