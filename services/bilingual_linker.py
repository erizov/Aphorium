"""
Service for linking English and Russian quotes.

Implements multiple strategies to find and link bilingual quote pairs:
1. Author + Source matching
2. Text similarity matching
3. Web scraping for official translations (future)
4. Translation API fallback (future)
"""

from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, case

from repositories.quote_repository import QuoteRepository
from repositories.author_repository import AuthorRepository
from repositories.translation_repository import TranslationRepository
from repositories.translation_word_repository import TranslationWordRepository
from models import Quote, Author, QuoteTranslation
from utils.text_utils import normalize_text
from logger_config import logger


class BilingualLinker:
    """
    Service for linking English and Russian quotes.
    
    Creates bidirectional links and assigns bilingual_group_id for fast retrieval.
    """

    def __init__(self, db: Session):
        """
        Initialize linker with database session.
        
        Args:
            db: Database session
        """
        self.db = db
        self.quote_repo = QuoteRepository(db)
        self.author_repo = AuthorRepository(db)
        self.translation_repo = TranslationRepository(db)
        self.word_repo = TranslationWordRepository(db)

    def link_quotes(
        self,
        quote_en_id: int,
        quote_ru_id: int,
        confidence: int = 80,
        strategy: str = "manual"
    ) -> Tuple[Optional[QuoteTranslation], int]:
        """
        Link two quotes bidirectionally and assign bilingual_group_id.
        
        Args:
            quote_en_id: English quote ID
            quote_ru_id: Russian quote ID
            confidence: Confidence score (0-100)
            strategy: Linking strategy used ('manual', 'author_match', 'similarity', etc.)
            
        Returns:
            Tuple of (translation object, bilingual_group_id)
        """
        try:
            # Get quotes
            quote_en = self.quote_repo.get_by_id(quote_en_id)
            quote_ru = self.quote_repo.get_by_id(quote_ru_id)
            
            if not quote_en or not quote_ru:
                logger.warning(
                    f"Quotes not found: EN={quote_en_id}, RU={quote_ru_id}"
                )
                return None, None
            
            if quote_en.language != 'en' or quote_ru.language != 'ru':
                logger.warning(
                    f"Language mismatch: EN={quote_en.language}, RU={quote_ru.language}"
                )
                return None, None
            
            # Determine bilingual_group_id
            group_id = None
            if quote_en.bilingual_group_id:
                group_id = quote_en.bilingual_group_id
            elif quote_ru.bilingual_group_id:
                group_id = quote_ru.bilingual_group_id
            else:
                # Create new group ID (use max + 1)
                max_group = self.db.query(func.max(Quote.bilingual_group_id)).scalar()
                group_id = (max_group or 0) + 1
            
            # Assign group IDs
            quote_en.bilingual_group_id = group_id
            quote_ru.bilingual_group_id = group_id
            self.db.commit()
            
            # Create bidirectional translation links
            # EN -> RU
            translation_en_ru = self.translation_repo.create(
                quote_id=quote_en_id,
                translated_quote_id=quote_ru_id,
                confidence=confidence
            )
            
            # RU -> EN (bidirectional)
            try:
                translation_ru_en = self.translation_repo.create(
                    quote_id=quote_ru_id,
                    translated_quote_id=quote_en_id,
                    confidence=confidence
                )
            except Exception:
                # May already exist, that's OK
                pass
            
            logger.info(
                f"Linked quotes EN={quote_en_id} <-> RU={quote_ru_id} "
                f"(group_id={group_id}, confidence={confidence}, strategy={strategy})"
            )
            
            return translation_en_ru, group_id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to link quotes: {e}")
            raise

    def find_matches_by_author(
        self,
        author_id: int,
        min_confidence: int = 50
    ) -> int:
        """
        Find and link quotes from same author using multiple strategies.
        
        Args:
            author_id: Author ID
            min_confidence: Minimum confidence score
            
        Returns:
            Number of links created
        """
        try:
            # Get quotes in both languages
            en_quotes = (
                self.db.query(Quote)
                .filter(Quote.author_id == author_id, Quote.language == 'en')
                .all()
            )
            ru_quotes = (
                self.db.query(Quote)
                .filter(Quote.author_id == author_id, Quote.language == 'ru')
                .all()
            )
            
            if not en_quotes or not ru_quotes:
                return 0
            
            links_created = 0
            
            # Strategy 1: Match by source (same source = likely same quote)
            for en_quote in en_quotes:
                if not en_quote.source_id:
                    continue
                
                # Find RU quotes from same source
                ru_same_source = [
                    q for q in ru_quotes
                    if q.source_id == en_quote.source_id
                ]
                
                if ru_same_source:
                    # Match with best similarity
                    best_ru = self._find_best_match_by_similarity(
                        en_quote, ru_same_source
                    )
                    if best_ru:
                        try:
                            self.link_quotes(
                                en_quote.id,
                                best_ru.id,
                                confidence=min(90, min_confidence + 20),
                                strategy="author_source_match"
                            )
                            links_created += 1
                        except Exception as e:
                            logger.debug(f"Could not link quotes: {e}")
                            continue
            
            # Strategy 2: Match by text similarity (for quotes without source)
            for en_quote in en_quotes:
                if en_quote.bilingual_group_id:
                    continue  # Already linked
                
                best_ru = self._find_best_match_by_similarity(
                    en_quote, ru_quotes
                )
                if best_ru and not best_ru.bilingual_group_id:
                    try:
                        self.link_quotes(
                            en_quote.id,
                            best_ru.id,
                            confidence=min_confidence,
                            strategy="author_similarity_match"
                        )
                        links_created += 1
                    except Exception as e:
                        logger.debug(f"Could not link quotes: {e}")
                        continue
            
            logger.info(
                f"Created {links_created} links for author {author_id}"
            )
            return links_created
            
        except Exception as e:
            logger.error(f"Failed to find matches by author: {e}")
            raise

    def _find_best_match_by_similarity(
        self,
        source_quote: Quote,
        candidate_quotes: List[Quote]
    ) -> Optional[Quote]:
        """
        Find best matching quote by text similarity.
        
        Args:
            source_quote: Source quote to match
            candidate_quotes: List of candidate quotes
            
        Returns:
            Best matching quote or None
        """
        if not candidate_quotes:
            return None
        
        source_words = set(
            word.lower().strip('.,!?;:()[]{}"\'')
            for word in source_quote.text.split()
            if len(word.strip('.,!?;:()[]{}"\'')) > 0
        )
        
        best_match = None
        best_match_count = 0
        
        for candidate in candidate_quotes:
            if candidate.bilingual_group_id:
                continue  # Already linked
            
            candidate_words = set(
                word.lower().strip('.,!?;:()[]{}"\'')
                for word in candidate.text.split()
                if len(word.strip('.,!?;:()[]{}"\'')) > 0
            )
            
            # Count matching words
            matching_words = source_words & candidate_words
            match_count = len(matching_words)
            
            # Require at least 4 matching words
            if match_count >= 4 and match_count > best_match_count:
                best_match = candidate
                best_match_count = match_count
        
        return best_match if best_match_count >= 4 else None

    def link_all_bilingual_authors(self) -> int:
        """
        Link quotes for all authors that have quotes in both languages.
        
        Returns:
            Total number of links created
        """
        try:
            # Find authors with quotes in both languages
            # Using subqueries for better compatibility
            authors_with_en = (
                self.db.query(Quote.author_id)
                .filter(
                    Quote.author_id.isnot(None),
                    Quote.language == 'en'
                )
                .distinct()
                .subquery()
            )
            
            authors_with_ru = (
                self.db.query(Quote.author_id)
                .filter(
                    Quote.author_id.isnot(None),
                    Quote.language == 'ru'
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
            
            total_links = 0
            for (author_id,) in authors_with_both:
                if author_id:
                    links = self.find_matches_by_author(author_id)
                    total_links += links
            
            logger.info(f"Total links created: {total_links}")
            return total_links
            
        except Exception as e:
            logger.error(f"Failed to link all authors: {e}")
            raise

    def populate_group_ids_from_translations(self) -> int:
        """
        Populate bilingual_group_id for existing translations.
        
        Scans existing QuoteTranslation records and assigns group IDs.
        
        Returns:
            Number of groups created
        """
        try:
            # Get all translations
            translations = self.db.query(QuoteTranslation).all()
            
            groups_created = 0
            max_group = self.db.query(func.max(Quote.bilingual_group_id)).scalar()
            next_group_id = (max_group or 0) + 1
            
            for trans in translations:
                quote_en = self.quote_repo.get_by_id(trans.quote_id)
                quote_ru = self.quote_repo.get_by_id(trans.translated_quote_id)
                
                if not quote_en or not quote_ru:
                    continue
                
                # Determine group ID
                if quote_en.bilingual_group_id:
                    group_id = quote_en.bilingual_group_id
                elif quote_ru.bilingual_group_id:
                    group_id = quote_ru.bilingual_group_id
                else:
                    group_id = next_group_id
                    next_group_id += 1
                    groups_created += 1
                
                # Assign group IDs
                quote_en.bilingual_group_id = group_id
                quote_ru.bilingual_group_id = group_id
            
            self.db.commit()
            logger.info(f"Populated {groups_created} new bilingual groups")
            return groups_created
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to populate group IDs: {e}")
            raise

