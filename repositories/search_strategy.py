"""
Search strategy pattern for different database backends.

Provides database-agnostic search interface with backend-specific
implementations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from models import Quote
from utils.text_utils import detect_language
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
        search_query = self.db.query(Quote)

        # Only filter by language if explicitly requested
        if language:
            search_query = search_query.filter(Quote.language == language)
        # Otherwise, search both languages (no language filter)

        # Search across all language configurations to find matches in both languages
        # Use OR to match in any language configuration
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
        
        # Order by relevance across all language configs
        # This ensures we get the best matches from both languages
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
        search_query = self.db.query(Quote)

        # Only filter by language if explicitly requested
        if language:
            search_query = search_query.filter(Quote.language == language)
        # Otherwise, search both languages (no language filter)

        # Use LIKE for text search (SQLite doesn't have full-text search
        # without FTS5 extension)
        # Search for all terms in the query
        search_terms = query.strip().split()
        for term in search_terms:
            search_query = search_query.filter(
                Quote.text.ilike(f"%{term}%")
            )

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

