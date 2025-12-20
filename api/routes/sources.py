"""
Source API routes.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from repositories.source_repository import SourceRepository
from api.models.schemas import SourceSchema
from logger_config import logger

router = APIRouter()


@router.get("", response_model=list[SourceSchema])
def search_sources(
    title: Optional[str] = Query(None, description="Source title search"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    db: Session = Depends(get_db)
) -> list[SourceSchema]:
    """
    Search sources.

    Args:
        title: Source title search term
        limit: Maximum number of results
        db: Database session

    Returns:
        List of matching sources
    """
    try:
        source_repo = SourceRepository(db)

        if title:
            sources = source_repo.search(title, limit=limit)
        else:
            # Return empty list if no search term
            sources = []

        return sources
    except Exception as e:
        logger.error(f"Search sources endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{source_id}", response_model=SourceSchema)
def get_source(
    source_id: int,
    db: Session = Depends(get_db)
) -> SourceSchema:
    """
    Get source by ID.

    Args:
        source_id: Source ID
        db: Database session

    Returns:
        Source object
    """
    try:
        source_repo = SourceRepository(db)
        source = source_repo.get_by_id(source_id)

        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        return source
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get source endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

