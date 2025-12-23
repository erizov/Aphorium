"""
Refactored search service for quotes.

Simplified by extracting BilingualPairBuilder and QueryTranslationService.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from models import Quote
from repositories.quote_repository import QuoteRepository
from services.bilingual_pair_builder import BilingualPairBuilder
from services.query_translation_service import QueryTranslationService
from logger_config import logger


class SearchService:
    """
    Service for quote search operations.
    
    Refactored to use extracted services for better maintainability.
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: Database session
        """
        self.db = db
        self.quote_repo = QuoteRepository(db)
        self.pair_builder = BilingualPairBuilder(db)
        self.query_translator = QueryTranslationService(db)

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

            # Get translated queries for bilingual search
            queries = self.query_translator.get_search_queries(query)
            
            # Search with all query variants
            # Get more quotes to find pairs
            search_limit = limit * 2
            all_quotes = []
            seen_quote_ids = set()
            
            for q in queries:
                quotes = self.quote_repo.search(
                    query=q,
                    language=lang_filter,
                    limit=search_limit
                )
                
                # Add unique quotes
                for quote in quotes:
                    if quote.id not in seen_quote_ids:
                        all_quotes.append(quote)
                        seen_quote_ids.add(quote.id)
            
            # Build bilingual pairs
            results = self.pair_builder.build_pairs(
                all_quotes,
                prefer_bilingual=prefer_bilingual
            )
            
            # Limit results
            results = results[:limit]
            
            logger.info(
                f"Search '{query}' returned {len(results)} bilingual pairs"
            )
            return results

        except Exception as e:
            logger.error(f"Search service error: {e}", exc_info=True)
            # Return empty list instead of raising exception
            return []

    def get_bilingual_pairs(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[dict]:
        """
        Get quotes with both English and Russian versions.
        
        Uses bilingual_group_id for fast retrieval.

        Args:
            limit: Maximum number of pairs
            offset: Result offset for pagination

        Returns:
            List of bilingual pair dictionaries
        """
        try:
            # Get quotes with bilingual_group_id (fast path)
            quotes_with_groups = (
                self.db.query(Quote)
                .filter(Quote.bilingual_group_id.isnot(None))
                .order_by(Quote.bilingual_group_id)
                .offset(offset)
                .limit(limit)
                .all()
            )
            
            # Build pairs from groups
            seen_groups = set()
            results = []
            
            for quote in quotes_with_groups:
                if quote.bilingual_group_id in seen_groups:
                    continue
                
                pair = self.pair_builder._build_pair_from_group(
                    quote.bilingual_group_id
                )
                if pair:
                    seen_groups.add(quote.bilingual_group_id)
                    results.append(pair)
                    
                    if len(results) >= limit:
                        break
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get bilingual pairs: {e}")
            return []

