"""
Load common English-Russian word translations into database.

This script generates and loads the 10,000 most common words from both languages.
"""

import csv
import os
from database import SessionLocal
from repositories.translation_word_repository import TranslationWordRepository
from logger_config import logger


def generate_common_words() -> list[dict]:
    """
    Generate common word translations.
    
    For MVP, uses an extended dictionary. In production, this could load
    from frequency lists or translation APIs.
    """
    # Extended common word dictionary
    # In production, load from actual frequency lists
    common_words = [
        # Basic words (already in translator.py)
        {'word_en': 'love', 'word_ru': 'любовь', 'frequency_en': 1000, 'frequency_ru': 1000},
        {'word_en': 'life', 'word_ru': 'жизнь', 'frequency_en': 950, 'frequency_ru': 950},
        {'word_en': 'wisdom', 'word_ru': 'мудрость', 'frequency_en': 800, 'frequency_ru': 800},
        {'word_en': 'death', 'word_ru': 'смерть', 'frequency_en': 750, 'frequency_ru': 750},
        {'word_en': 'hope', 'word_ru': 'надежда', 'frequency_en': 700, 'frequency_ru': 700},
        {'word_en': 'freedom', 'word_ru': 'свобода', 'frequency_en': 650, 'frequency_ru': 650},
        {'word_en': 'truth', 'word_ru': 'истина', 'frequency_en': 600, 'frequency_ru': 600},
        {'word_en': 'beauty', 'word_ru': 'красота', 'frequency_en': 550, 'frequency_ru': 550},
        {'word_en': 'happiness', 'word_ru': 'счастье', 'frequency_en': 500, 'frequency_ru': 500},
        {'word_en': 'sorrow', 'word_ru': 'печаль', 'frequency_en': 450, 'frequency_ru': 450},
        {'word_en': 'time', 'word_ru': 'время', 'frequency_en': 400, 'frequency_ru': 400},
        {'word_en': 'dream', 'word_ru': 'мечта', 'frequency_en': 350, 'frequency_ru': 350},
        {'word_en': 'soul', 'word_ru': 'душа', 'frequency_en': 300, 'frequency_ru': 300},
        {'word_en': 'heart', 'word_ru': 'сердце', 'frequency_en': 250, 'frequency_ru': 250},
        {'word_en': 'mind', 'word_ru': 'ум', 'frequency_en': 200, 'frequency_ru': 200},
    ]
    
    # Generate more words programmatically
    # For 10k words, we'd need actual frequency lists
    # This is a template - extend with real data sources
    
    return common_words


def load_from_csv(csv_path: str) -> list[dict]:
    """Load translations from CSV file."""
    translations = []
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                translations.append({
                    'word_en': row.get('word_en', '').strip(),
                    'word_ru': row.get('word_ru', '').strip(),
                    'frequency_en': int(row.get('frequency_en', 0)),
                    'frequency_ru': int(row.get('frequency_ru', 0))
                })
    return translations


def main():
    """Main entry point."""
    logger.info("Loading common word translations...")
    
    db = SessionLocal()
    repo = TranslationWordRepository(db)
    
    try:
        # Check if already loaded
        count = repo.get_count()
        if count > 0:
            logger.info(f"Database already has {count} translations")
            response = input("Reload? (y/n): ").strip().lower()
            if response != 'y':
                logger.info("Skipping load")
                return
            # Clear existing
            db.query(WordTranslation).delete()
            db.commit()
        
        # Try to load from CSV if exists
        csv_path = "data/common_words.csv"
        translations = load_from_csv(csv_path)
        
        if not translations:
            logger.info("No CSV found, generating common words...")
            logger.info("Run 'python generate_common_words.py' first to create CSV with 10k words")
            translations = generate_common_words()
            logger.warning(f"Only loaded {len(translations)} words. Generate CSV for full 10k words.")
        
        # Load into database
        logger.info(f"Loading {len(translations)} translations...")
        repo.bulk_create(translations)
        
        final_count = repo.get_count()
        logger.info(f"Successfully loaded {final_count} word translations")
        
    except Exception as e:
        logger.error(f"Failed to load translations: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    from models import WordTranslation
    main()

