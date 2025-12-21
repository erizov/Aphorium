"""
Search strategy pattern for different database backends.

Provides database-agnostic search interface with backend-specific
implementations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from models import Quote
from utils.text_utils import detect_language, sanitize_search_query, escape_like_pattern
from logger_config import logger


class SearchStrategy:
    """Base class for search strategies."""

    def search(
        self,
        query: str,
        language: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Quote]:
        """
        Search quotes.

        Args:
            query: Search query
            language: Language filter
            limit: Result limit
            offset: Result offset

        Returns:
            List of matching quotes
        """
        raise NotImplementedError


class PostgreSQLSearchStrategy(SearchStrategy):
    """PostgreSQL full-text search strategy."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def search(
        self,
        query: str,
        language: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Quote]:
        """
        Search using PostgreSQL full-text search.
        
        Always searches both English and Russian quotes regardless of query language,
        unless explicitly filtered by language parameter.
        """
        # Sanitize query to prevent SQL injection and handle special characters
        query = sanitize_search_query(query)
        
        if not query:
            # Return empty results for empty/invalid queries
            return []
        
        # Translate query to search in both languages
        from utils.translator import get_bilingual_search_queries
        original_query, translated_query = get_bilingual_search_queries(query, self.db)
        
        # Use both queries for search
        queries_to_search = [original_query]
        if translated_query and translated_query.lower() != original_query.lower():
            queries_to_search.append(translated_query)
        
        search_query = self.db.query(Quote)

        # Only filter by language if explicitly requested
        if language:
            search_query = search_query.filter(Quote.language == language)
        # Otherwise, search both languages (no language filter)

        # Search across all language configurations to find matches in both languages
        # Use OR to match in any language configuration and any query variant
        # plainto_tsquery automatically handles special characters and SQL keywords
        try:
            # Build OR conditions for each query variant
            search_conditions = []
            for q in queries_to_search:
                search_conditions.extend([
                    # English text search config
                    func.to_tsvector('english', Quote.text).match(
                        func.plainto_tsquery('english', q)
                    ),
                    # Russian text search config
                    func.to_tsvector('russian', Quote.text).match(
                        func.plainto_tsquery('russian', q)
                    ),
                    # Simple (language-agnostic) config for broader matching
                    func.to_tsvector('simple', Quote.text).match(
                        func.plainto_tsquery('simple', q)
                    )
                ])
            
            # Combine all conditions with OR
            search_query = search_query.filter(or_(*search_conditions))
        except Exception as e:
            logger.warning(f"Full-text search failed for query '{query}': {e}. Trying simple search.")
            # Fallback: if plainto_tsquery fails (e.g., invalid characters), 
            # use a basic text search that matches the phrase
            # Use both original and translated queries
            fallback_conditions = []
            for q in queries_to_search:
                escaped_q = q.replace('%', '\\%').replace('_', '\\_')
                fallback_conditions.append(
                    Quote.text.ilike(f"%{escaped_q}%")
                )
            search_query = search_query.filter(or_(*fallback_conditions))
        
        # Order by relevance across all language configs
        # This ensures we get the best matches from both languages
        try:
            # Build ordering using the first query (original) for ranking
            # This prioritizes exact matches over translated matches
            primary_query = queries_to_search[0]
            search_query = search_query.order_by(
                # Prioritize matches in the query's detected language
                func.ts_rank(
                    func.to_tsvector('simple', Quote.text),
                    func.plainto_tsquery('simple', primary_query)
                ).desc().nullslast(),
                # Then by English config relevance
                func.ts_rank(
                    func.to_tsvector('english', Quote.text),
                    func.plainto_tsquery('english', primary_query)
                ).desc().nullslast(),
                # Then by Russian config relevance
                func.ts_rank(
                    func.to_tsvector('russian', Quote.text),
                    func.plainto_tsquery('russian', primary_query)
                ).desc().nullslast()
            )
        except Exception:
            # If ranking fails, just order by ID as fallback
            search_query = search_query.order_by(Quote.id.desc())

        return search_query.limit(limit).offset(offset).all()


class SQLiteSearchStrategy(SearchStrategy):
    """SQLite search strategy using LIKE queries."""

    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db

    def search(
        self,
        query: str,
        language: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Quote]:
        """
        Search using SQLite LIKE queries.
        
        Always searches both English and Russian quotes regardless of query language,
        unless explicitly filtered by language parameter.
        """
        # Sanitize query to prevent SQL injection and handle special characters
        query = sanitize_search_query(query)
        
        if not query:
            # Return empty results for empty/invalid queries
            return []
        
        # Translate query to search in both languages
        from utils.translator import get_bilingual_search_queries
        original_query, translated_query = get_bilingual_search_queries(query, self.db)
        
        # Use both queries for search
        queries_to_search = [original_query]
        if translated_query and translated_query.lower() != original_query.lower():
            queries_to_search.append(translated_query)
        
        search_query = self.db.query(Quote)

        # Only filter by language if explicitly requested
        if language:
            search_query = search_query.filter(Quote.language == language)
        # Otherwise, search both languages (no language filter)

        # Use LIKE for text search (SQLite doesn't have full-text search
        # without FTS5 extension)
        # For multi-word queries, match the phrase in order
        # Escape special LIKE characters to prevent issues
        # Search with both original and translated queries
        
        # Build OR conditions for each query variant
        search_conditions = []
        for q in queries_to_search:
            escaped_query = escape_like_pattern(q)
            search_conditions.append(
                Quote.text.ilike(f"%{escaped_query}%", escape='\\')
            )
        
        # Combine all conditions with OR
        search_query = search_query.filter(or_(*search_conditions))
        
        # If no results, fall back to matching all words (but this is less ideal)
        # We'll let the caller handle empty results

        # Order by text length (shorter matches first as proxy for relevance)
        # This will return results from both languages
        search_query = search_query.order_by(
            func.length(Quote.text).asc()
        )

        return search_query.limit(limit).offset(offset).all()


def get_search_strategy(db: Session) -> SearchStrategy:
    """
    Get appropriate search strategy based on database type.

    Args:
        db: Database session

    Returns:
        Search strategy instance
    """
    from database import engine
    
    if engine.url.drivername == "postgresql":
        return PostgreSQLSearchStrategy(db)
    else:
        return SQLiteSearchStrategy(db)

