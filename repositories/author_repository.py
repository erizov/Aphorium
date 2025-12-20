"""
Author repository for database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models import Author
from logger_config import logger


class AuthorRepository:
    """Repository for author operations."""

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: Database session
        """
        self.db = db

    def create(
        self,
        name: str,
        language: str,
        bio: Optional[str] = None,
        wikiquote_url: Optional[str] = None
    ) -> Author:
        """
        Create a new author.

        Args:
            name: Author name
            language: Language code ('en' or 'ru')
            bio: Optional biography
            wikiquote_url: Optional WikiQuote URL

        Returns:
            Created author object
        """
        try:
            author = Author(
                name=name,
                language=language,
                bio=bio,
                wikiquote_url=wikiquote_url
            )
            self.db.add(author)
            self.db.commit()
            self.db.refresh(author)
            logger.debug(f"Created author {author.id}: {author.name}")
            return author
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create author: {e}")
            raise

    def get_by_id(self, author_id: int) -> Optional[Author]:
        """
        Get author by ID.

        Args:
            author_id: Author ID

        Returns:
            Author object or None if not found
        """
        try:
            return self.db.query(Author).filter(
                Author.id == author_id
            ).first()
        except Exception as e:
            logger.error(f"Failed to get author {author_id}: {e}")
            raise

    def search(self, name: str, limit: int = 20) -> List[Author]:
        """
        Search authors by name.

        Args:
            name: Search term
            limit: Maximum number of results

        Returns:
            List of matching authors
        """
        try:
            search_term = f"%{name}%"
            return (
                self.db.query(Author)
                .filter(Author.name.ilike(search_term))
                .limit(limit)
                .all()
            )
        except Exception as e:
            logger.error(f"Failed to search authors: {e}")
            raise

    def get_or_create(
        self,
        name: str,
        language: str,
        bio: Optional[str] = None,
        wikiquote_url: Optional[str] = None
    ) -> Author:
        """
        Get existing author or create new one.

        Args:
            name: Author name
            language: Language code
            bio: Optional biography
            wikiquote_url: Optional WikiQuote URL

        Returns:
            Author object
        """
        try:
            # Try to find existing author
            author = (
                self.db.query(Author)
                .filter(
                    Author.name == name,
                    Author.language == language
                )
                .first()
            )

            if author:
                return author

            # Create new author
            return self.create(name, language, bio, wikiquote_url)
        except Exception as e:
            logger.error(f"Failed to get or create author: {e}")
            raise

