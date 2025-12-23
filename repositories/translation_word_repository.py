"""
Repository for word translation operations.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from models import WordTranslation
from logger_config import logger


class TranslationWordRepository:
    """Repository for word translation operations."""

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    def get_translation(self, word: str) -> Optional[str]:
        """
        Get translation for a word.
        
        Args:
            word: Word to translate (English or Russian)
            
        Returns:
            Translated word or None if not found
        """
        try:
            word_lower = word.lower().strip()
            
            # Try English -> Russian
            translation = self.db.query(WordTranslation).filter(
                WordTranslation.word_en == word_lower
            ).first()
            
            if translation:
                return translation.word_ru
            
            # Try Russian -> English
            translation = self.db.query(WordTranslation).filter(
                WordTranslation.word_ru == word_lower
            ).first()
            
            if translation:
                return translation.word_en
            
            return None
        except Exception as e:
            logger.error(f"Failed to get translation for '{word}': {e}")
            return None

    def create_or_update(
        self,
        word_en: str,
        word_ru: str,
        frequency_en: int = 0,
        frequency_ru: int = 0
    ) -> WordTranslation:
        """
        Create or update a translation entry.
        
        Args:
            word_en: English word
            word_ru: Russian word
            frequency_en: English word frequency
            frequency_ru: Russian word frequency
            
        Returns:
            WordTranslation object
        """
        try:
            word_en_lower = word_en.lower().strip()
            word_ru_lower = word_ru.lower().strip()
            
            # Check if English word already exists (only check word_en, not word_ru)
            # Multiple English words can have the same Russian translation
            existing = self.db.query(WordTranslation).filter(
                WordTranslation.word_en == word_en_lower
            ).first()
            
            if existing:
                # Update frequencies if higher, and update Russian if different
                if frequency_en > existing.frequency_en:
                    existing.frequency_en = frequency_en
                if frequency_ru > existing.frequency_ru:
                    existing.frequency_ru = frequency_ru
                # Update Russian translation if provided and different
                if word_ru_lower and word_ru_lower != existing.word_ru:
                    existing.word_ru = word_ru_lower
                self.db.commit()
                return existing
            
            # Create new
            translation = WordTranslation(
                word_en=word_en_lower,
                word_ru=word_ru_lower,
                frequency_en=frequency_en,
                frequency_ru=frequency_ru
            )
            self.db.add(translation)
            self.db.commit()
            self.db.refresh(translation)
            return translation
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create/update translation: {e}")
            raise

    def bulk_create(self, translations: List[dict]) -> int:
        """
        Bulk create translations.
        
        Args:
            translations: List of dicts with 'word_en', 'word_ru', 'frequency_en', 'frequency_ru'
            
        Returns:
            Number of translations created
        """
        try:
            count = 0
            batch_size = 1000
            
            for i in range(0, len(translations), batch_size):
                batch = translations[i:i + batch_size]
                for trans in batch:
                    self.create_or_update(
                        word_en=trans.get('word_en', ''),
                        word_ru=trans.get('word_ru', ''),
                        frequency_en=trans.get('frequency_en', 0),
                        frequency_ru=trans.get('frequency_ru', 0)
                    )
                    count += 1
                
                if (i + batch_size) % 10000 == 0:
                    logger.info(f"Loaded {i + batch_size} translations...")
            
            self.db.commit()
            logger.info(f"Bulk created {count} translations")
            return count
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to bulk create translations: {e}")
            raise

    def get_count(self) -> int:
        """Get total number of translations."""
        return self.db.query(WordTranslation).count()
    
    def delete_from_id(self, start_id: int) -> int:
        """
        Delete all translations starting from specified ID.
        
        Args:
            start_id: Starting ID to delete from
            
        Returns:
            Number of records deleted
        """
        try:
            count = self.db.query(WordTranslation).filter(
                WordTranslation.id >= start_id
            ).delete(synchronize_session=False)
            self.db.commit()
            return count
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete records from ID {start_id}: {e}")
            raise

