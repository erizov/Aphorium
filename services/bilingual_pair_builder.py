"""
Bilingual pair builder service.

Extracted from SearchService to improve maintainability.
Builds bilingual quote pairs from search results.
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from models import Quote
from repositories.translation_repository import TranslationRepository
from logger_config import logger


class BilingualPairBuilder:
    """
    Builds bilingual quote pairs from search results.
    
    Uses bilingual_group_id for fast retrieval when available,
    falls back to QuoteTranslation table for legacy data.
    """

    def __init__(self, db: Session):
        """
        Initialize builder with database session.
        
        Args:
            db: Database session
        """
        self.db = db
        self.translation_repo = TranslationRepository(db)

    def build_pairs(
        self,
        quotes: List[Quote],
        prefer_bilingual: bool = True
    ) -> List[Dict]:
        """
        Convert quotes to bilingual pairs.
        
        Args:
            quotes: List of Quote objects from search
            prefer_bilingual: Prioritize quotes with translations
            
        Returns:
            List of bilingual pair dictionaries
        """
        results = []
        seen_quote_ids = set()
        seen_groups = set()
        
        # First pass: Build pairs using bilingual_group_id (fast path)
        for quote in quotes:
            if quote.id in seen_quote_ids:
                continue
            
            if quote.bilingual_group_id:
                # Fast path: get both quotes from same group
                pair = self._build_pair_from_group(quote.bilingual_group_id)
                if pair:
                    # Mark quotes as seen
                    if pair.get("english"):
                        seen_quote_ids.add(pair["english"]["id"])
                    if pair.get("russian"):
                        seen_quote_ids.add(pair["russian"]["id"])
                    seen_groups.add(quote.bilingual_group_id)
                    results.append(pair)
                    continue
        
        # Second pass: Build pairs using translation table (legacy/fallback)
        for quote in quotes:
            if quote.id in seen_quote_ids:
                continue
            
            if quote.bilingual_group_id and quote.bilingual_group_id in seen_groups:
                continue
            
            pair = self._build_pair_from_translation(quote)
            if pair:
                # Mark quotes as seen
                if pair.get("english"):
                    seen_quote_ids.add(pair["english"]["id"])
                if pair.get("russian"):
                    seen_quote_ids.add(pair["russian"]["id"])
                results.append(pair)
        
        # Sort by bilingual preference if requested
        if prefer_bilingual:
            results.sort(
                key=lambda x: (
                    0 if (x.get("english") and x.get("russian")) else 1,
                    -(x.get("english", {}).get("id", 0) or 
                      x.get("russian", {}).get("id", 0))
                )
            )
        
        return results

    def _build_pair_from_group(
        self,
        group_id: int
    ) -> Optional[Dict]:
        """
        Build bilingual pair from bilingual_group_id.
        
        Args:
            group_id: Bilingual group ID
            
        Returns:
            Bilingual pair dictionary or None
        """
        try:
            # Get both quotes from the group
            quotes = (
                self.db.query(Quote)
                .filter(Quote.bilingual_group_id == group_id)
                .all()
            )
            
            if not quotes:
                return None
            
            pair = {
                "english": None,
                "russian": None,
                "is_translated": False,  # From database, not generated
                "translation_source": "database_group"
            }
            
            for quote in quotes:
                if quote.language == 'en':
                    pair["english"] = self._quote_to_dict(quote)
                elif quote.language == 'ru':
                    pair["russian"] = self._quote_to_dict(quote)
            
            # Only return if we have at least one language
            if pair["english"] or pair["russian"]:
                return pair
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to build pair from group {group_id}: {e}")
            return None

    def _build_pair_from_translation(
        self,
        quote: Quote
    ) -> Optional[Dict]:
        """
        Build bilingual pair using translation table (legacy method).
        
        Args:
            quote: Source quote
            
        Returns:
            Bilingual pair dictionary or None
        """
        try:
            pair = {
                "english": None,
                "russian": None,
                "is_translated": False,
                "translation_source": None
            }
            
            if quote.language == 'en':
                pair["english"] = self._quote_to_dict(quote)
                # Find Russian translation
                ru_quote = self.translation_repo.get_translated_quote(
                    quote.id, 'ru'
                )
                if ru_quote:
                    pair["russian"] = self._quote_to_dict(ru_quote)
                    pair["is_translated"] = True
                    pair["translation_source"] = "database_translation"
            
            elif quote.language == 'ru':
                pair["russian"] = self._quote_to_dict(quote)
                # Find English translation
                en_quote = self.translation_repo.get_translated_quote(
                    quote.id, 'en'
                )
                if en_quote:
                    pair["english"] = self._quote_to_dict(en_quote)
                    pair["is_translated"] = True
                    pair["translation_source"] = "database_translation"
            
            # Only return if we have at least one language
            if pair["english"] or pair["russian"]:
                return pair
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to build pair from translation: {e}")
            return None

    def _quote_to_dict(self, quote: Quote) -> Dict:
        """
        Convert Quote object to dictionary matching QuoteSchema.
        
        Args:
            quote: Quote object
            
        Returns:
            Quote dictionary compatible with QuoteSchema
        """
        result = {
            "id": quote.id,
            "text": quote.text,
            "language": quote.language,
            "author": None,
            "source": None,
            "has_translation": None,
            "translation_count": None,
            "created_at": quote.created_at.isoformat() if quote.created_at else None
        }
        
        # Add author if exists (matching AuthorSchema)
        # Use name_en for EN quotes, name_ru for RU quotes
        if quote.author:
            author_name = (
                quote.author.name_en if quote.language == 'en' 
                else quote.author.name_ru
            ) if quote.author else None
            
            result["author"] = {
                "id": quote.author.id,
                "name": author_name,  # Language-specific name for display
                "name_en": quote.author.name_en,
                "name_ru": quote.author.name_ru,
                "bio": quote.author.bio
            }
        
        # Add source if exists (matching SourceSchema)
        if quote.source:
            result["source"] = {
                "id": quote.source.id,
                "title": quote.source.title,
                "language": quote.source.language,
                "source_type": quote.source.source_type
            }
        
        return result

