"""
Source repository for database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from models import Source
from logger_config import logger


class SourceRepository:
    """Repository for source operations."""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: Database session
        """
        self.db = db

    def create(
        self,
        title: str,
        language: str,
        author_id: Optional[int] = None,
        source_type: Optional[str] = None,
        wikiquote_url: Optional[str] = None
    ) -> Source:
        """
        Create a new source.

        Args:
            title: Source title
            language: Language code ('en' or 'ru')
            author_id: Optional author ID
            source_type: Optional source type ('book', 'play', etc.)
            wikiquote_url: Optional WikiQuote URL

        Returns:
            Created source object
        """
        try:
            source = Source(
                title=title,
                language=language,
                author_id=author_id,
                source_type=source_type,
                wikiquote_url=wikiquote_url
            )
            self.db.add(source)
            self.db.commit()
            self.db.refresh(source)
            logger.debug(f"Created source {source.id}: {source.title}")
            return source
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create source: {e}")
            raise

    def get_by_id(self, source_id: int) -> Optional[Source]:
        """
        Get source by ID.

        Args:
            source_id: Source ID

        Returns:
            Source object or None if not found
        """
        try:
            return self.db.query(Source).filter(
                Source.id == source_id
            ).first()
        except Exception as e:
            logger.error(f"Failed to get source {source_id}: {e}")
            raise

    def search(self, title: str, limit: int = 20) -> List[Source]:
        """
        Search sources by title.

        Args:
            title: Search term
            limit: Maximum number of results

        Returns:
            List of matching sources
        """
        try:
            search_term = f"%{title}%"
            return (
                self.db.query(Source)
                .filter(Source.title.ilike(search_term))
                .limit(limit)
                .all()
            )
        except Exception as e:
            logger.error(f"Failed to search sources: {e}")
            raise

    def get_or_create(
        self,
        title: str,
        language: str,
        author_id: Optional[int] = None,
        source_type: Optional[str] = None,
        wikiquote_url: Optional[str] = None
    ) -> Source:
        """
        Get existing source or create new one.

        Args:
            title: Source title
            language: Language code
            author_id: Optional author ID
            source_type: Optional source type
            wikiquote_url: Optional WikiQuote URL

        Returns:
            Source object
        """
        try:
            # Try to find existing source
            source = (
                self.db.query(Source)
                .filter(
                    Source.title == title,
                    Source.language == language
                )
                .first()
            )

            if source:
                return source

            # Create new source
            return self.create(
                title, language, author_id, source_type, wikiquote_url
            )
        except Exception as e:
            logger.error(f"Failed to get or create source: {e}")
            raise

