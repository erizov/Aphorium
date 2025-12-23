"""
Query translation service.

Extracted from search logic to improve maintainability.
Handles query translation for bilingual search.
"""

from typing import List
from sqlalchemy.orm import Session

from utils.translator import get_bilingual_search_queries
from logger_config import logger


class QueryTranslationService:
    """
    Handles query translation for bilingual search.
    
    Translates search queries to enable cross-language search.
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.
        
        Args:
            db: Database session
        """
        self.db = db

    def get_search_queries(self, query: str) -> List[str]:
        """
        Get original and translated queries for bilingual search.
        
        Args:
            query: Original search query
            
        Returns:
            List of queries to search (original + translated)
        """
        try:
            original_query, translated_query = get_bilingual_search_queries(
                query, self.db
            )
            
            queries = [original_query]
            
            # Add translated query if different
            if translated_query and translated_query.lower() != original_query.lower():
                queries.append(translated_query)
                logger.debug(
                    f"Query translation: '{original_query}' -> '{translated_query}'"
                )
            
            return queries
            
        except Exception as e:
            logger.warning(f"Failed to translate query '{query}': {e}")
            # Return original query only on error
            return [query]

