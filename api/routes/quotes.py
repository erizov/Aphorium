"""
Quote API routes.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from services.search_service import SearchService
from services.quote_service import QuoteService
from api.models.schemas import (
    QuoteSchema, QuoteWithTranslationsSchema, BilingualPairSchema
)
from utils.error_handling import QuoteNotFoundError
from logger_config import logger

router = APIRouter()


@router.get("/search", response_model=list[BilingualPairSchema])
def search_quotes(
    q: str = Query(..., description="Search query"),
    lang: Optional[str] = Query(
        None, description="Language filter: 'en', 'ru', or 'both'"
    ),
    prefer_bilingual: bool = Query(
        True, description="Prioritize quotes with translations"
    ),
    limit: int = Query(50, ge=1, le=300, description="Result limit"),
    db: Session = Depends(get_db)
) -> list[dict]:
    """
    Search quotes.

    Args:
        q: Search query text
        lang: Language filter
        prefer_bilingual: Prioritize bilingual quotes
        limit: Maximum number of results
        db: Database session

    Returns:
        List of matching quotes
    """
    try:
        if not q or not q.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Validate query length (prevent extremely long queries)
        MAX_QUERY_LENGTH = 500
        if len(q) > MAX_QUERY_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Query too long. Maximum length is {MAX_QUERY_LENGTH} characters."
            )

        search_service = SearchService(db)
        # Always search both languages unless explicitly filtered
        # This ensures results include quotes in both English and Russian
        # regardless of the query language
        search_lang = None if (lang is None or lang == "both") else lang
        
        try:
            results = search_service.search(
                query=q.strip(),
                language=search_lang,  # None means search both languages
                prefer_bilingual=prefer_bilingual,
                limit=limit
            )
            # Always return a list, even if empty
            # This prevents 500 errors when no results are found
            return results if results else []
        except Exception as search_error:
            logger.warning(f"Search failed for query '{q}': {search_error}")
            # Return empty list instead of error for failed searches
            # This handles cases like invalid queries, no matches, etc.
            return []
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search endpoint error: {e}", exc_info=True)
        # Return empty list instead of 500 error for user-friendliness
        return []


@router.get("/random", response_model=BilingualPairSchema)
def get_random_quote(
    db: Session = Depends(get_db)
) -> dict:
    """
    Get a random quote (preferably bilingual).

    Args:
        db: Database session

    Returns:
        Random bilingual quote pair
    """
    try:
        from sqlalchemy import func
        from models import Quote
        from database import engine
        
        # Check database type for random function
        is_sqlite = 'sqlite' in str(engine.url).lower()
        
        # For SQLite, use different approach
        if is_sqlite:
            # SQLite doesn't support func.random() in ORDER BY, use Python random
            import random
            bilingual_quotes = (
                db.query(Quote)
                .filter(Quote.bilingual_group_id.isnot(None))
                .all()
            )
            if bilingual_quotes:
                bilingual_quote = random.choice(bilingual_quotes)
            else:
                bilingual_quote = None
        else:
            # PostgreSQL: use func.random()
            bilingual_quote = (
                db.query(Quote)
                .filter(Quote.bilingual_group_id.isnot(None))
                .order_by(func.random())
                .first()
            )
        
        if bilingual_quote:
            # Build pair from bilingual group
            from services.bilingual_pair_builder import BilingualPairBuilder
            pair_builder = BilingualPairBuilder(db)
            pair = pair_builder._build_pair_from_group(bilingual_quote.bilingual_group_id)
            if pair:
                return pair
        
        # Fallback: get any random quote
        if is_sqlite:
            import random
            all_quotes = db.query(Quote).all()
            if not all_quotes:
                raise HTTPException(status_code=404, detail="No quotes found in database")
            random_quote = random.choice(all_quotes)
        else:
            random_quote = (
                db.query(Quote)
                .order_by(func.random())
                .first()
            )
        
        if not random_quote:
            raise HTTPException(status_code=404, detail="No quotes found in database")
        
        # Build pair for single quote
        search_service = SearchService(db)
        pair_dict = {
            "english": None,
            "russian": None,
            "is_translated": False,
            "translation_source": None
        }
        
        if random_quote.language == 'en':
            pair_dict["english"] = search_service._quote_to_dict(random_quote)
        else:
            pair_dict["russian"] = search_service._quote_to_dict(random_quote)
        
        return pair_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get random quote endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{quote_id}", response_model=QuoteWithTranslationsSchema)
def get_quote(
    quote_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """
    Get quote by ID with translations.

    Args:
        quote_id: Quote ID
        db: Database session

    Returns:
        Quote with translations
    """
    try:
        quote_service = QuoteService(db)
        quote = quote_service.get_quote_with_translations(quote_id)

        if not quote:
            raise QuoteNotFoundError(quote_id)

        return quote
    except (HTTPException, QuoteNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Get quote endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/bilingual/pairs", response_model=list[BilingualPairSchema])
def get_bilingual_pairs(
    limit: int = Query(50, ge=1, le=300, description="Result limit"),
    offset: int = Query(0, ge=0, description="Result offset"),
    db: Session = Depends(get_db)
) -> list[dict]:
    """
    Get quotes with both English and Russian versions.

    Args:
        limit: Maximum number of pairs
        offset: Result offset for pagination
        db: Database session

    Returns:
        List of bilingual quote pairs
    """
    try:
        search_service = SearchService(db)
        pairs = search_service.get_bilingual_pairs(limit=limit, offset=offset)
        return pairs
    except Exception as e:
        logger.error(f"Get bilingual pairs endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")