"""
Directly fix author name encoding by using paired authors' names.

This script:
1. Finds authors with encoding mismatches
2. Uses their paired author's name to fix the encoding
3. Ensures each author has both EN and RU rows
"""

import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from repositories.author_repository import AuthorRepository
from logger_config import logger

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


def find_paired_author_by_quotes(
    db,
    author: Author
) -> Optional[Author]:
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


def fix_author_names_direct(db, min_id: int = 186) -> dict:
    """
    Directly fix author name encoding using paired authors.
    
    Args:
        db: Database session
        min_id: Minimum author ID to process
        
    Returns:
        Statistics dictionary
    """
    stats = {
        'total': 0,
        'encoding_fixed': 0,
        'en_created': 0,
        'ru_created': 0,
        'already_correct': 0,
        'needs_manual_review': 0
    }
    
    try:
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
                    
                    # Find paired author
                    paired_author = find_paired_author_by_quotes(db, author)
                    
                    if paired_author:
                        paired_detected = detect_text_language(paired_author.name)
                        
                        # If they are swapped (author has name in paired's language, paired has name in author's language)
                        if (detected_lang == paired_author.language and 
                            paired_detected == author.language):
                            # They are swapped - swap their names
                            temp_name = author.name
                            author.name = paired_author.name
                            paired_author.name = temp_name
                            stats['encoding_fixed'] += 1
                            logger.info(
                                f"Swapped names: Author {author.id} ({author.language}) "
                                f"'{author.name}' <-> Author {paired_author.id} "
                                f"({paired_author.language}) '{paired_author.name}'"
                            )
                            db.commit()
                            processed_ids.add(paired_author.id)
                        elif paired_detected == paired_author.language:
                            # Paired author has correct encoding - use it for this author
                            # But wait, we need the name in the correct language for this author
                            # If author is RU and has EN name, we need RU name
                            # If author is EN and has RU name, we need EN name
                            
                            # Check if paired author has name_en or name_ru that we can use
                            if author.language == 'en':
                                # Author should have English name
                                if paired_author.name_en and detect_text_language(paired_author.name_en) == 'en':
                                    author.name = paired_author.name_en
                                    stats['encoding_fixed'] += 1
                                    logger.info(
                                        f"Fixed author {author.id} EN name from paired author's name_en"
                                    )
                                    db.commit()
                                elif detect_text_language(paired_author.name) == 'ru':
                                    # Paired has RU name, we need to find EN version
                                    # Look for another author with same name in EN
                                    en_author = (
                                        db.query(Author)
                                        .filter(
                                            Author.name == author.name,
                                            Author.language == 'en',
                                            Author.id != author.id
                                        )
                                        .first()
                                    )
                                    if en_author and detect_text_language(en_author.name) == 'en':
                                        author.name = en_author.name
                                        stats['encoding_fixed'] += 1
                                        logger.info(
                                            f"Fixed author {author.id} EN name from existing EN author"
                                        )
                                        db.commit()
                                    else:
                                        stats['needs_manual_review'] += 1
                                        logger.warning(
                                            f"Author {author.id} needs manual review: "
                                            f"EN author with RU name '{author.name}'"
                                        )
                                else:
                                    stats['needs_manual_review'] += 1
                                    logger.warning(
                                        f"Author {author.id} needs manual review: "
                                        f"EN author with wrong encoding"
                                    )
                            else:  # author.language == 'ru'
                                # Author should have Russian name
                                if paired_author.name_ru and detect_text_language(paired_author.name_ru) == 'ru':
                                    author.name = paired_author.name_ru
                                    stats['encoding_fixed'] += 1
                                    logger.info(
                                        f"Fixed author {author.id} RU name from paired author's name_ru"
                                    )
                                    db.commit()
                                elif detect_text_language(paired_author.name) == 'en':
                                    # Paired has EN name, we need to find RU version
                                    # Look for another author with same name in RU
                                    ru_author = (
                                        db.query(Author)
                                        .filter(
                                            Author.name == author.name,
                                            Author.language == 'ru',
                                            Author.id != author.id
                                        )
                                        .first()
                                    )
                                    if ru_author and detect_text_language(ru_author.name) == 'ru':
                                        author.name = ru_author.name
                                        stats['encoding_fixed'] += 1
                                        logger.info(
                                            f"Fixed author {author.id} RU name from existing RU author"
                                        )
                                        db.commit()
                                    else:
                                        stats['needs_manual_review'] += 1
                                        logger.warning(
                                            f"Author {author.id} needs manual review: "
                                            f"RU author with EN name '{author.name}'"
                                        )
                                else:
                                    stats['needs_manual_review'] += 1
                                    logger.warning(
                                        f"Author {author.id} needs manual review: "
                                        f"RU author with wrong encoding"
                                    )
                        else:
                            stats['needs_manual_review'] += 1
                            logger.warning(
                                f"Author {author.id} needs manual review: "
                                f"Both author and paired have wrong encoding"
                            )
                    else:
                        # No paired author - try to find correct name
                        correct_lang = 'en' if author.language == 'en' else 'ru'
                        correct_author = (
                            db.query(Author)
                            .filter(
                                Author.name == author.name,
                                Author.language == correct_lang,
                                Author.id != author.id
                            )
                            .first()
                        )
                        
                        if correct_author and detect_text_language(correct_author.name) == correct_lang:
                            author.name = correct_author.name
                            stats['encoding_fixed'] += 1
                            logger.info(f"Fixed author {author.id} encoding from existing author")
                            db.commit()
                        else:
                            stats['needs_manual_review'] += 1
                            logger.warning(
                                f"Author {author.id} needs manual review: "
                                f"language={author.language}, name='{author.name}'"
                            )
                else:
                    # Encoding is correct
                    stats['already_correct'] += 1
                
                # Step 2: Ensure author has both EN and RU versions
                paired_author = find_paired_author_by_quotes(db, author)
                
                if not paired_author:
                    # No paired author found - create one
                    if author.language == 'en':
                        # Create RU version
                        similar_ru = (
                            db.query(Author)
                            .filter(
                                Author.language == 'ru',
                                Author.name.ilike(f"%{author.name.split()[0] if author.name.split() else ''}%")
                            )
                            .first()
                        )
                        
                        if similar_ru:
                            paired_author = similar_ru
                            logger.info(
                                f"Found existing RU author {paired_author.id} for EN author {author.id}"
                            )
                        else:
                            # Create new RU author - use name_ru if available, otherwise same name
                            ru_name = author.name_ru if author.name_ru else author.name
                            paired_author = author_repo.create(
                                name=ru_name,
                                language='ru',
                                bio=author.bio,
                                wikiquote_url=author.wikiquote_url
                            )
                            stats['ru_created'] += 1
                            logger.info(
                                f"Created RU author {paired_author.id} for EN author {author.id}"
                            )
                    else:
                        # Create EN version
                        similar_en = (
                            db.query(Author)
                            .filter(
                                Author.language == 'en',
                                Author.name.ilike(f"%{author.name.split()[0] if author.name.split() else ''}%")
                            )
                            .first()
                        )
                        
                        if similar_en:
                            paired_author = similar_en
                            logger.info(
                                f"Found existing EN author {paired_author.id} for RU author {author.id}"
                            )
                        else:
                            # Create new EN author - use name_en if available, otherwise same name
                            en_name = author.name_en if author.name_en else author.name
                            paired_author = author_repo.create(
                                name=en_name,
                                language='en',
                                bio=author.bio,
                                wikiquote_url=author.wikiquote_url
                            )
                            stats['en_created'] += 1
                            logger.info(
                                f"Created EN author {paired_author.id} for RU author {author.id}"
                            )
                    
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
                logger.warning(f"Error processing author {author.id}: {e}")
                db.rollback()
                continue
        
        logger.info(f"Processing complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to fix authors: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Directly fix author name encoding using paired authors'
    )
    parser.add_argument(
        '--min-id',
        type=int,
        default=186,
        help='Minimum author ID to process (default: 186)'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Directly fixing author name encoding")
    logger.info(f"Processing authors with ID >= {args.min_id}")
    logger.info("=" * 60)
    
    if not HAS_LANGDETECT:
        logger.warning("langdetect not available, using basic character detection")
    
    db = SessionLocal()
    
    try:
        stats = fix_author_names_direct(db, min_id=args.min_id)
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total authors processed: {stats['total']}")
        logger.info(f"  Encoding fixed: {stats['encoding_fixed']}")
        logger.info(f"  Already correct: {stats['already_correct']}")
        logger.info(f"  EN versions created: {stats['en_created']}")
        logger.info(f"  RU versions created: {stats['ru_created']}")
        logger.info(f"  Needs manual review: {stats['needs_manual_review']}")
        logger.info("=" * 60)
        
        if stats['needs_manual_review'] > 0:
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

