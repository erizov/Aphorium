"""
Quote repository for database operations.

Handles CRUD operations and search queries for quotes.
"""

import re
from typing import List, Optional, Set
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session, aliased

from models import Quote, Author, Source, QuoteTranslation
from repositories.search_strategy import get_search_strategy
from logger_config import logger


class QuoteRepository:
    """Repository for quote operations."""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: Database session
        """
        self.db = db

    def create(
        self,
        text: str,
        author_id: Optional[int] = None,
        source_id: Optional[int] = None,
        language: str = "en"
    ) -> Quote:
        """
        Create a new quote, checking for duplicates first.

        Args:
            text: Quote text
            author_id: Optional author ID
            source_id: Optional source ID
            language: Language code ('en' or 'ru')

        Returns:
            Created quote object or existing quote if duplicate found
        """
        try:
            # Normalize text for comparison (strip, lowercase)
            normalized_text = text.strip().lower()
            
            # Check for duplicate quotes based on text similarity only
            # (not author - quotes can have same text but different authors)
            # Get all quotes, then compare text similarity
            # Also check for similarity (more than half of the same words)
            candidates = self.db.query(Quote).all()
            
            # Pre-tokenize incoming quote
            incoming_tokens = self._tokenize_text(normalized_text)
            incoming_token_count = len(incoming_tokens)
            
            similar_candidate = None
            for candidate in candidates:
                candidate_text = candidate.text.strip().lower()
                
                # Exact match
                if candidate_text == normalized_text:
                    similar_candidate = candidate
                    break
                
                # Similarity check: more than half the same words
                if incoming_token_count == 0:
                    continue
                
                candidate_tokens = self._tokenize_text(candidate_text)
                overlap = len(incoming_tokens & candidate_tokens)
                
                if overlap > incoming_token_count / 2:
                    similar_candidate = candidate
                    break
            
            if similar_candidate:
                logger.debug(
                    "Duplicate/similar quote found (ID: %s), "
                    "rejecting new quote",
                    getattr(similar_candidate, "id", None)
                )
                return similar_candidate
            
            # Create new quote
            quote = Quote(
                text=text,
                author_id=author_id,
                source_id=source_id,
                language=language
            )
            self.db.add(quote)
            self.db.commit()
            self.db.refresh(quote)
            logger.debug(f"Created quote {quote.id}")
            return quote
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create quote: {e}")
            raise

    @staticmethod
    def _tokenize_text(text: str) -> Set[str]:
        """
        Tokenize text into a set of lowercase words.
        
        Args:
            text: Input text
        
        Returns:
            Set of unique lowercase words.
        """
        tokens = re.findall(r"\b\w+\b", text.lower())
        return set(tokens)

    def get_by_id(self, quote_id: int) -> Optional[Quote]:
        """
        Get quote by ID.

        Args:
            quote_id: Quote ID

        Returns:
            Quote object or None if not found
        """
        try:
            return self.db.query(Quote).filter(Quote.id == quote_id).first()
        except Exception as e:
            logger.error(f"Failed to get quote {quote_id}: {e}")
            raise

    def search(
        self,
        query: str,
        language: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Quote]:
        """
        Search quotes using database-appropriate search strategy.

        Supports both English and Russian languages in a single search.
        Automatically uses PostgreSQL full-text search or SQLite LIKE queries.

        Args:
            query: Search query text
            language: Filter by language ('en', 'ru', or None for both)
            limit: Maximum number of results
            offset: Result offset for pagination

        Returns:
            List of matching quotes
        """
        try:
            # Get appropriate search strategy based on database type
            strategy = get_search_strategy(self.db)
            results = strategy.search(query, language, limit, offset)
            
            logger.debug(f"Search '{query}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            raise

    def get_with_translations(
        self,
        quote_id: int
    ) -> tuple[Optional[Quote], List[Quote]]:
        """
        Get quote with its translations.

        Args:
            quote_id: Quote ID

        Returns:
            Tuple of (quote, list of translated quotes)
        """
        try:
            quote = self.get_by_id(quote_id)
            if not quote:
                return None, []

            # Get translations
            translations = (
                self.db.query(Quote)
                .join(
                    QuoteTranslation,
                    Quote.id == QuoteTranslation.translated_quote_id
                )
                .filter(QuoteTranslation.quote_id == quote_id)
                .all()
            )

            return quote, translations
        except Exception as e:
            logger.error(f"Failed to get translations for quote {quote_id}: {e}")
            raise

    def get_quotes_by_group_id(
        self,
        group_id: int
    ) -> List[Quote]:
        """
        Get all quotes in a bilingual group.
        
        Args:
            group_id: Bilingual group ID
            
        Returns:
            List of quotes in the group
        """
        try:
            return (
                self.db.query(Quote)
                .filter(Quote.bilingual_group_id == group_id)
                .order_by(Quote.language)
                .all()
            )
        except Exception as e:
            logger.error(f"Failed to get quotes by group ID: {e}")
            return []

    def get_bilingual_pairs(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[tuple[Quote, Quote]]:
        """
        Get quotes that have both English and Russian versions.

        Args:
            limit: Maximum number of pairs
            offset: Result offset for pagination

        Returns:
            List of (english_quote, russian_quote) tuples
        """
        try:
            from sqlalchemy.orm import aliased

            # Use aliases for the two Quote instances
            Quote1 = aliased(Quote)
            Quote2 = aliased(Quote)

            # Find quotes with translations between en and ru
            pairs = (
                self.db.query(Quote1, Quote2)
                .join(
                    QuoteTranslation,
                    Quote1.id == QuoteTranslation.quote_id
                )
                .join(
                    Quote2,
                    Quote2.id == QuoteTranslation.translated_quote_id
                )
                .filter(
                    or_(
                        and_(
                            Quote1.language == "en",
                            Quote2.language == "ru"
                        ),
                        and_(
                            Quote1.language == "ru",
                            Quote2.language == "en"
                        )
                    )
                )
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Normalize to (en, ru) order
            result = []
            for q1, q2 in pairs:
                if q1.language == "en":
                    result.append((q1, q2))
                else:
                    result.append((q2, q1))

            logger.debug(f"Found {len(result)} bilingual pairs")
            return result
        except Exception as e:
            logger.error(f"Failed to get bilingual pairs: {e}")
            raise

    def update_search_vector(self, quote_id: int) -> None:
        """
        Update search vector for a quote (for full-text search).

        Args:
            quote_id: Quote ID
        """
        try:
            quote = self.get_by_id(quote_id)
            if quote:
                # Update search vector using PostgreSQL function
                from sqlalchemy import update
                stmt = (
                    update(Quote)
                    .where(Quote.id == quote_id)
                    .values(
                        search_vector=func.to_tsvector('english', Quote.text)
                    )
                )
                self.db.execute(stmt)
                self.db.commit()
                logger.debug(f"Updated search vector for quote {quote_id}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update search vector: {e}")
            raise

