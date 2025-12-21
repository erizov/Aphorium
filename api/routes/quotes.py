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
from logger_config import logger

router = APIRouter()


@router.get("/search", response_model=list[QuoteSchema])
def search_quotes(
    q: str = Query(..., description="Search query"),
    lang: Optional[str] = Query(
        None, description="Language filter: 'en', 'ru', or 'both'"
    ),
    prefer_bilingual: bool = Query(
        True, description="Prioritize quotes with translations"
    ),
    limit: int = Query(50, ge=1, le=100, description="Result limit"),
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
        results = search_service.search(
            query=q.strip(),
            language=search_lang,  # None means search both languages
            prefer_bilingual=prefer_bilingual,
            limit=limit
        )
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


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
            raise HTTPException(status_code=404, detail="Quote not found")

        return quote
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get quote endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/bilingual/pairs", response_model=list[BilingualPairSchema])
def get_bilingual_pairs(
    limit: int = Query(50, ge=1, le=100, description="Result limit"),
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

