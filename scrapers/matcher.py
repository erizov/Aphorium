"""
Translation matcher for finding English-Russian quote pairs.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from repositories.quote_repository import QuoteRepository
from repositories.author_repository import AuthorRepository
from repositories.translation_repository import TranslationRepository
from models import Quote
from logger_config import logger


class TranslationMatcher:
    """Matches quotes between languages based on author and source."""

    def __init__(self, db: Session):
        """
        Initialize matcher with database session.

        Args:
            db: Database session
        """
        self.db = db
        self.quote_repo = QuoteRepository(db)
        self.author_repo = AuthorRepository(db)
        self.translation_repo = TranslationRepository(db)

    def match_quotes_by_author(
        self,
        author_id: int,
        min_confidence: int = 30
    ) -> int:
        """
        Match quotes by same author in different languages.

        Args:
            author_id: Author ID
            min_confidence: Minimum confidence score (0-100)

        Returns:
            Number of matches created
        """
        try:
            # Get all quotes for this author
            en_quotes = (
                self.db.query(Quote)
                .filter(Quote.author_id == author_id, Quote.language == "en")
                .all()
            )
            ru_quotes = (
                self.db.query(Quote)
                .filter(Quote.author_id == author_id, Quote.language == "ru")
                .all()
            )

            matches_created = 0

            # Simple matching: if same source, match quotes by position
            # This is a basic heuristic - can be improved
            for en_quote in en_quotes:
                if not en_quote.source_id:
                    continue

                # Find Russian quotes from same source
                ru_same_source = [
                    q for q in ru_quotes
                    if q.source_id == en_quote.source_id
                ]

                if ru_same_source:
                    # Match with first quote from same source
                    # In future, could use text similarity
                    ru_quote = ru_same_source[0]
                    try:
                        self.translation_repo.create(
                            quote_id=en_quote.id,
                            translated_quote_id=ru_quote.id,
                            confidence=min_confidence
                        )
                        matches_created += 1
                    except Exception as e:
                        logger.debug(f"Could not create match: {e}")
                        continue

            logger.info(
                f"Matched {matches_created} quote pairs for author {author_id}"
            )
            return matches_created

        except Exception as e:
            logger.error(f"Failed to match quotes by author: {e}")
            raise

    def match_all_authors(self) -> int:
        """
        Match quotes for all authors that have quotes in both languages.

        Returns:
            Total number of matches created
        """
        try:
            from sqlalchemy import func, case

            # Find authors with quotes in both languages
            # Using a simpler approach with subqueries
            authors_with_en = (
                self.db.query(Quote.author_id)
                .filter(
                    Quote.author_id.isnot(None),
                    Quote.language == "en"
                )
                .distinct()
                .subquery()
            )

            authors_with_ru = (
                self.db.query(Quote.author_id)
                .filter(
                    Quote.author_id.isnot(None),
                    Quote.language == "ru"
                )
                .distinct()
                .subquery()
            )

            # Find intersection - authors with quotes in both languages
            authors_with_both = (
                self.db.query(authors_with_en.c.author_id)
                .filter(
                    authors_with_en.c.author_id.in_(
                        self.db.query(authors_with_ru.c.author_id)
                    )
                )
                .all()
            )

            total_matches = 0
            for (author_id,) in authors_with_both:
                if author_id:
                    matches = self.match_quotes_by_author(author_id)
                    total_matches += matches

            logger.info(f"Total matches created: {total_matches}")
            return total_matches

        except Exception as e:
            logger.error(f"Failed to match all authors: {e}")
            raise

