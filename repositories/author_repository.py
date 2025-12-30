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
        name_en: Optional[str] = None,
        name_ru: Optional[str] = None,
        bio: Optional[str] = None,
        wikiquote_url: Optional[str] = None
    ) -> Author:
        """
        Create a new author.

        Args:
            name_en: English name
            name_ru: Russian name
            bio: Optional biography
            wikiquote_url: Optional WikiQuote URL

        Returns:
            Created author object
        """
        try:
            author = Author(
                name_en=name_en,
                name_ru=name_ru,
                bio=bio,
                wikiquote_url=wikiquote_url
            )
            self.db.add(author)
            self.db.commit()
            self.db.refresh(author)
            logger.debug(
                f"Created author {author.id}: name_en='{author.name_en}', "
                f"name_ru='{author.name_ru}'"
            )
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
        Search authors by name (searches both name_en and name_ru).

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
                .filter(
                    or_(
                        Author.name_en.ilike(search_term),
                        Author.name_ru.ilike(search_term)
                    )
                )
                .limit(limit)
                .all()
            )
        except Exception as e:
            logger.error(f"Failed to search authors: {e}")
            raise

    def get_or_create(
        self,
        name_en: Optional[str] = None,
        name_ru: Optional[str] = None,
        bio: Optional[str] = None,
        wikiquote_url: Optional[str] = None
    ) -> Author:
        """
        Get existing author or create new one.

        Args:
            name_en: English name
            name_ru: Russian name
            bio: Optional biography
            wikiquote_url: Optional WikiQuote URL

        Returns:
            Author object
        """
        try:
            # Try to find existing author by name_en or name_ru
            author = None
            if name_en:
                author = (
                    self.db.query(Author)
                    .filter(Author.name_en == name_en)
                    .first()
                )
            if not author and name_ru:
                author = (
                    self.db.query(Author)
                    .filter(Author.name_ru == name_ru)
                    .first()
                )

            if author:
                # Update missing name fields if needed
                if name_en and not author.name_en:
                    author.name_en = name_en
                if name_ru and not author.name_ru:
                    author.name_ru = name_ru
                if author.name_en != name_en or author.name_ru != name_ru:
                    self.db.commit()
                return author

            # Create new author
            return self.create(name_en, name_ru, bio, wikiquote_url)
        except Exception as e:
            logger.error(f"Failed to get or create author: {e}")
            raise
    
    def get_unknown_author(self, language: str) -> Author:
        """
        Get or create an "Unknown" author for quotes without attribution.
        
        Args:
            language: Language code ('en' or 'ru') - used to determine which name to set
            
        Returns:
            Author object with appropriate name set
        """
        if language == "en":
            return self.get_or_create(
                name_en="Unknown",
                name_ru=None,
                bio=None,
                wikiquote_url=None
            )
        else:  # language == "ru"
            return self.get_or_create(
                name_en=None,
                name_ru="Неизвестный",
                bio=None,
                wikiquote_url=None
            )

