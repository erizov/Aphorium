"""
Author API routes.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from repositories.author_repository import AuthorRepository
from api.models.schemas import AuthorSchema
from logger_config import logger

router = APIRouter()


@router.get("", response_model=list[AuthorSchema])
def search_authors(
    name: Optional[str] = Query(None, description="Author name search"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    db: Session = Depends(get_db)
) -> list[AuthorSchema]:
    """
    Search authors.

    Args:
        name: Author name search term
        limit: Maximum number of results
        db: Database session

    Returns:
        List of matching authors
    """
    try:
        author_repo = AuthorRepository(db)

        if name:
            authors = author_repo.search(name, limit=limit)
        else:
            # Return empty list if no search term
            authors = []

        return authors
    except Exception as e:
        logger.error(f"Search authors endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{author_id}", response_model=AuthorSchema)
def get_author(
    author_id: int,
    db: Session = Depends(get_db)
) -> AuthorSchema:
    """
    Get author by ID.

    Args:
        author_id: Author ID
        db: Database session

    Returns:
        Author object
    """
    try:
        author_repo = AuthorRepository(db)
        author = author_repo.get_by_id(author_id)

        if not author:
            raise HTTPException(status_code=404, detail="Author not found")

        return author
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get author endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

