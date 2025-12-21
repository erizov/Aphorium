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
        
        search_query = self.db.query(Quote)

        # Only filter by language if explicitly requested
        if language:
            search_query = search_query.filter(Quote.language == language)
        # Otherwise, search both languages (no language filter)

        # Search across all language configurations to find matches in both languages
        # Use OR to match in any language configuration
        # plainto_tsquery automatically handles special characters and SQL keywords
        try:
            # For multi-word queries, use phrase search to match words in order
            # plainto_tsquery creates AND queries by default, which is what we want
            search_query = search_query.filter(
                or_(
                    # English text search config
                    func.to_tsvector('english', Quote.text).match(
                        func.plainto_tsquery('english', query)
                    ),
                    # Russian text search config
                    func.to_tsvector('russian', Quote.text).match(
                        func.plainto_tsquery('russian', query)
                    ),
                    # Simple (language-agnostic) config for broader matching
                    func.to_tsvector('simple', Quote.text).match(
                        func.plainto_tsquery('simple', query)
                    )
                )
            )
        except Exception as e:
            logger.warning(f"Full-text search failed for query '{query}': {e}. Trying simple search.")
            # Fallback: if plainto_tsquery fails (e.g., invalid characters), 
            # use a basic text search that matches the phrase
            escaped_query = query.replace('%', '\\%').replace('_', '\\_')
            search_query = search_query.filter(
                Quote.text.ilike(f"%{escaped_query}%")
            )
        
        # Order by relevance across all language configs
        # This ensures we get the best matches from both languages
        try:
            search_query = search_query.order_by(
                # Prioritize matches in the query's detected language
                func.ts_rank(
                    func.to_tsvector('simple', Quote.text),
                    func.plainto_tsquery('simple', query)
                ).desc().nullslast(),
                # Then by English config relevance
                func.ts_rank(
                    func.to_tsvector('english', Quote.text),
                    func.plainto_tsquery('english', query)
                ).desc().nullslast(),
                # Then by Russian config relevance
                func.ts_rank(
                    func.to_tsvector('russian', Quote.text),
                    func.plainto_tsquery('russian', query)
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
        
        search_query = self.db.query(Quote)

        # Only filter by language if explicitly requested
        if language:
            search_query = search_query.filter(Quote.language == language)
        # Otherwise, search both languages (no language filter)

        # Use LIKE for text search (SQLite doesn't have full-text search
        # without FTS5 extension)
        # For multi-word queries, match the phrase in order
        # Escape special LIKE characters to prevent issues
        
        # First try exact phrase match (words in order)
        escaped_query = escape_like_pattern(query)
        search_query = search_query.filter(
            Quote.text.ilike(f"%{escaped_query}%", escape='\\')
        )
        
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

