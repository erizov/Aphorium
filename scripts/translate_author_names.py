"""
Translate author names using the translation service.

This script:
1. Finds authors with encoding mismatches (RU authors with EN names, EN authors with RU names)
2. Uses the translation service to translate names to the correct language
3. Updates the database with translated names
4. Ensures each author has both EN and RU rows
"""

import sys
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from repositories.author_repository import AuthorRepository
from logger_config import logger

# Import translation service
try:
    from translit_service import TranslationService, TRANSLATION_AVAILABLE
except ImportError:
    TRANSLATION_AVAILABLE = False
    logger.error("Translation service not available")

try:
    from langdetect import detect, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    logger.warning("langdetect not available, using basic character detection")


def detect_text_language(text: str) -> Optional[str]:
    """
    Detect language of text.
    
    Args:
        text: Text to analyze
        
    Returns:
        'en', 'ru', or None if uncertain
    """
    if not text or not text.strip():
        return None
    
    if HAS_LANGDETECT:
        try:
            lang = detect(text)
            if lang == 'en':
                return 'en'
            elif lang == 'ru':
                return 'ru'
        except LangDetectException:
            pass
    
    # Fallback: character-based detection
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
    has_latin = any(char.isalpha() and ord(char) < 128 for char in text)
    
    if has_cyrillic and not has_latin:
        return 'ru'
    elif has_latin and not has_cyrillic:
        return 'en'
    elif has_cyrillic and has_latin:
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        latin_count = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        return 'ru' if cyrillic_count > latin_count else 'en'
    
    return None


def find_paired_author_by_quotes(db, author: Author) -> Optional[Author]:
    """
    Find paired author in opposite language through quote relationships.
    
    Args:
        db: Database session
        author: Source author
        
    Returns:
        Paired author in opposite language or None
    """
    try:
        quotes = db.query(Quote).filter(Quote.author_id == author.id).all()
        if not quotes:
            return None
        
        bilingual_groups = set()
        for quote in quotes:
            if quote.bilingual_group_id:
                bilingual_groups.add(quote.bilingual_group_id)
        
        if not bilingual_groups:
            return None
        
        target_language = 'ru' if author.language == 'en' else 'en'
        linked_quotes = (
            db.query(Quote)
            .filter(
                Quote.bilingual_group_id.in_(bilingual_groups),
                Quote.language == target_language,
                Quote.author_id != author.id,
                Quote.author_id.isnot(None)
            )
            .all()
        )
        
        if not linked_quotes:
            return None
        
        author_counts = {}
        for quote in linked_quotes:
            if quote.author_id:
                author_counts[quote.author_id] = author_counts.get(quote.author_id, 0) + 1
        
        if not author_counts:
            return None
        
        most_common_author_id = max(author_counts.items(), key=lambda x: x[1])[0]
        paired_author = db.query(Author).filter(Author.id == most_common_author_id).first()
        
        if paired_author and paired_author.language == target_language:
            return paired_author
        
        return None
        
    except Exception as e:
        logger.warning(f"Error finding paired author for {author.id}: {e}")
        return None


def translate_author_names(
    db,
    min_id: int = 186,
    delay: float = 0.5,
    provider: str = 'google'
) -> dict:
    """
    Translate author names to fix encoding mismatches.
    
    Args:
        db: Database session
        min_id: Minimum author ID to process
        delay: Delay between translations (seconds)
        provider: Translation provider ('google', 'deepl', etc.)
        
    Returns:
        Statistics dictionary
    """
    if not TRANSLATION_AVAILABLE:
        logger.error("Translation service not available!")
        return {'error': 'Translation service not available'}
    
    stats = {
        'total': 0,
        'translated': 0,
        'swapped': 0,
        'already_correct': 0,
        'en_created': 0,
        'ru_created': 0,
        'translation_errors': 0,
        'needs_manual_review': 0
    }
    
    try:
        # Initialize translation service
        translation_service = TranslationService(provider=provider, delay=delay)
        logger.info(f"Translation service initialized with provider: {provider}")
        
        author_repo = AuthorRepository(db)
        
        # Get all authors starting from min_id
        all_authors = db.query(Author).filter(Author.id >= min_id).order_by(Author.id).all()
        stats['total'] = len(all_authors)
        
        logger.info(f"Processing {stats['total']} authors (ID >= {min_id})...")
        
        processed_ids = set()
        
        for author in all_authors:
            if author.id in processed_ids:
                continue
            
            try:
                detected_lang = detect_text_language(author.name)
                
                # Check if encoding matches language
                if detected_lang and detected_lang != author.language:
                    logger.warning(
                        f"Author {author.id}: language={author.language}, "
                        f"name encoding={detected_lang}, name='{author.name}'"
                    )
                    
                    # Find paired author first
                    paired_author = find_paired_author_by_quotes(db, author)
                    
                    # Check if they are swapped
                    if paired_author:
                        paired_detected = detect_text_language(paired_author.name)
                        
                        # Case 1: They are swapped
                        if (detected_lang == paired_author.language and 
                            paired_detected == author.language):
                            # Swap their names
                            temp_name = author.name
                            author.name = paired_author.name
                            paired_author.name = temp_name
                            stats['swapped'] += 1
                            logger.info(
                                f"✅ Swapped: Author {author.id} ({author.language}) "
                                f"'{author.name}' <-> Author {paired_author.id} "
                                f"({paired_author.language}) '{paired_author.name}'"
                            )
                            db.commit()
                            processed_ids.add(paired_author.id)
                            continue
                    
                    # Case 2: Need to translate
                    # Determine source and target languages
                    source_lang = detected_lang  # Current name encoding
                    target_lang = author.language  # What it should be
                    
                    logger.info(
                        f"Translating author {author.id}: '{author.name}' "
                        f"from {source_lang} to {target_lang}"
                    )
                    
                    # Translate the name
                    translated_name = translation_service.translate(
                        author.name,
                        source_lang=source_lang,
                        target_lang=target_lang
                    )
                    
                    if translated_name and translated_name.strip():
                        # Verify the translated name is in the correct language
                        translated_detected = detect_text_language(translated_name)
                        if translated_detected == target_lang:
                            author.name = translated_name
                            stats['translated'] += 1
                            logger.info(
                                f"✅ Translated: Author {author.id} ({author.language}) "
                                f"name set to '{author.name}'"
                            )
                            db.commit()
                        else:
                            stats['translation_errors'] += 1
                            logger.warning(
                                f"⚠️  Translation result has wrong encoding: "
                                f"'{translated_name}' (detected: {translated_detected}, "
                                f"expected: {target_lang})"
                            )
                    else:
                        stats['translation_errors'] += 1
                        logger.warning(
                            f"⚠️  Translation failed for author {author.id}: "
                            f"'{author.name}'"
                        )
                    
                    # Add delay to avoid rate limiting
                    time.sleep(delay)
                    
                else:
                    # Encoding is correct
                    stats['already_correct'] += 1
                
                # Step 2: Ensure author has both EN and RU versions
                paired_author = find_paired_author_by_quotes(db, author)
                
                # Try by name similarity if not found by quotes
                if not paired_author:
                    target_lang = 'ru' if author.language == 'en' else 'en'
                    similar = (
                        db.query(Author)
                        .filter(
                            Author.language == target_lang,
                            Author.name.ilike(f"%{author.name.split()[0] if author.name.split() else ''}%")
                        )
                        .first()
                    )
                    if similar:
                        paired_author = similar
                
                if not paired_author:
                    # No paired author found - create one
                    if author.language == 'en':
                        # Create RU version - translate the name
                        logger.info(
                            f"Creating RU version for EN author {author.id}: '{author.name}'"
                        )
                        translated_name = translation_service.translate(
                            author.name,
                            source_lang='en',
                            target_lang='ru'
                        )
                        
                        if translated_name and translated_name.strip():
                            ru_name = translated_name
                        else:
                            ru_name = author.name  # Fallback
                            logger.warning(
                                f"Translation failed, using original name for RU author"
                            )
                        
                        paired_author = author_repo.create(
                            name=ru_name,
                            language='ru',
                            bio=author.bio,
                            wikiquote_url=author.wikiquote_url
                        )
                        stats['ru_created'] += 1
                        logger.info(
                            f"Created RU author {paired_author.id} for EN author {author.id}: "
                            f"'{paired_author.name}'"
                        )
                        time.sleep(delay)
                    else:
                        # Create EN version - translate the name
                        logger.info(
                            f"Creating EN version for RU author {author.id}: '{author.name}'"
                        )
                        translated_name = translation_service.translate(
                            author.name,
                            source_lang='ru',
                            target_lang='en'
                        )
                        
                        if translated_name and translated_name.strip():
                            en_name = translated_name
                        else:
                            en_name = author.name  # Fallback
                            logger.warning(
                                f"Translation failed, using original name for EN author"
                            )
                        
                        paired_author = author_repo.create(
                            name=en_name,
                            language='en',
                            bio=author.bio,
                            wikiquote_url=author.wikiquote_url
                        )
                        stats['en_created'] += 1
                        logger.info(
                            f"Created EN author {paired_author.id} for RU author {author.id}: "
                            f"'{paired_author.name}'"
                        )
                        time.sleep(delay)
                    
                    db.commit()
                
                # Update name_en and name_ru fields
                if author.language == 'en':
                    if not author.name_en:
                        author.name_en = author.name
                    if paired_author and not author.name_ru:
                        author.name_ru = paired_author.name
                    if paired_author and not paired_author.name_en:
                        paired_author.name_en = author.name
                    if paired_author and not paired_author.name_ru:
                        paired_author.name_ru = paired_author.name
                else:  # RU
                    if not author.name_ru:
                        author.name_ru = author.name
                    if paired_author and not author.name_en:
                        author.name_en = paired_author.name
                    if paired_author and not paired_author.name_en:
                        paired_author.name_en = paired_author.name
                    if paired_author and not paired_author.name_ru:
                        paired_author.name_ru = author.name
                
                processed_ids.add(author.id)
                if paired_author:
                    processed_ids.add(paired_author.id)
                
                db.commit()
                
            except Exception as e:
                logger.warning(f"Error processing author {author.id}: {e}", exc_info=True)
                db.rollback()
                stats['needs_manual_review'] += 1
                continue
        
        logger.info(f"Processing complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to translate author names: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Translate author names to fix encoding mismatches'
    )
    parser.add_argument(
        '--min-id',
        type=int,
        default=186,
        help='Minimum author ID to process (default: 186)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between translations in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--provider',
        type=str,
        default='google',
        choices=['google', 'deepl', 'microsoft', 'mymemory', 'pons', 'linguee'],
        help='Translation provider (default: google)'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Translating author names to fix encoding")
    logger.info(f"Processing authors with ID >= {args.min_id}")
    logger.info(f"Translation provider: {args.provider}")
    logger.info(f"Delay between translations: {args.delay}s")
    logger.info("=" * 60)
    
    if not TRANSLATION_AVAILABLE:
        logger.error("Translation service not available! Install deep-translator")
        return
    
    db = SessionLocal()
    
    try:
        stats = translate_author_names(
            db,
            min_id=args.min_id,
            delay=args.delay,
            provider=args.provider
        )
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total authors processed: {stats.get('total', 0)}")
        logger.info(f"  Names translated: {stats.get('translated', 0)}")
        logger.info(f"  Names swapped: {stats.get('swapped', 0)}")
        logger.info(f"  Already correct: {stats.get('already_correct', 0)}")
        logger.info(f"  EN versions created: {stats.get('en_created', 0)}")
        logger.info(f"  RU versions created: {stats.get('ru_created', 0)}")
        logger.info(f"  Translation errors: {stats.get('translation_errors', 0)}")
        logger.info(f"  Needs manual review: {stats.get('needs_manual_review', 0)}")
        logger.info("=" * 60)
        
        if stats.get('translation_errors', 0) > 0:
            logger.warning(
                f"{stats['translation_errors']} translations had errors. "
                "Check the logs for details."
            )
        
        if stats.get('needs_manual_review', 0) > 0:
            logger.warning(
                f"{stats['needs_manual_review']} authors need manual review. "
                "Check the logs for details."
            )
        
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

