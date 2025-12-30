"""
Fix author name encoding and ensure each author has both EN and RU rows.

This script:
1. Fixes name encoding to match language (EN authors get English names, RU authors get Russian names)
2. Ensures each author has 2 rows: one EN with English encoding, one RU with Russian encoding
3. Creates missing author versions if needed
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Tuple

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


def fix_author_encoding_and_pairs(db, min_id: int = 186) -> dict:
    """
    Fix author name encoding and ensure each author has both EN and RU rows.
    
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
        'already_complete': 0,
        'needs_manual_review': 0
    }
    
    try:
        author_repo = AuthorRepository(db)
        
        # Get all authors starting from min_id
        all_authors = db.query(Author).filter(Author.id >= min_id).order_by(Author.id).all()
        stats['total'] = len(all_authors)
        
        logger.info(f"Processing {stats['total']} authors (ID >= {min_id})...")
        
        # Group authors by potential pairs
        processed_ids = set()
        
        for author in all_authors:
            if author.id in processed_ids:
                continue
            
            try:
                detected_lang = detect_text_language(author.name)
                
                # Step 1: Fix encoding if name doesn't match language
                if detected_lang and detected_lang != author.language:
                    logger.warning(
                        f"Author {author.id}: language={author.language}, "
                        f"name encoding={detected_lang}, name='{author.name}'"
                    )
                    
                    # Find paired author to get correct name
                    paired_author = find_paired_author_by_quotes(db, author)
                    
                    if paired_author:
                        # Check if paired author has the correct encoding
                        paired_detected = detect_text_language(paired_author.name)
                        
                        # If they are swapped (author has RU name but is EN, paired has EN name but is RU)
                        if (detected_lang == paired_author.language and 
                            paired_detected == author.language):
                            # They are swapped - swap their names
                            temp_name = author.name
                            author.name = paired_author.name
                            paired_author.name = temp_name
                            stats['encoding_fixed'] += 1
                            logger.info(
                                f"Swapped names: Author {author.id} ({author.language}) "
                                f"<-> Author {paired_author.id} ({paired_author.language})"
                            )
                            db.commit()
                        elif paired_detected == author.language:
                            # Paired author has the correct name for this author
                            author.name = paired_author.name
                            stats['encoding_fixed'] += 1
                            logger.info(
                                f"Fixed author {author.id} encoding using paired author {paired_author.id}"
                            )
                            db.commit()
                        else:
                            # Both have wrong encoding - look for correct name elsewhere
                            correct_lang = 'en' if author.language == 'en' else 'ru'
                            # Look for any author with this exact name in correct language
                            correct_author = (
                                db.query(Author)
                                .filter(
                                    Author.name == author.name,
                                    Author.language == correct_lang,
                                    Author.id != author.id
                                )
                                .first()
                            )
                            
                            if correct_author:
                                author.name = correct_author.name
                                stats['encoding_fixed'] += 1
                                logger.info(
                                    f"Fixed author {author.id} encoding from correct language author"
                                )
                                db.commit()
                            else:
                                stats['needs_manual_review'] += 1
                                logger.warning(
                                    f"Author {author.id} needs manual review: "
                                    f"language={author.language}, name='{author.name}'"
                                )
                    else:
                        # No paired author found - look for author with same name in correct language
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
                        
                        if correct_author:
                            author.name = correct_author.name
                            stats['encoding_fixed'] += 1
                            logger.info(f"Fixed author {author.id} encoding")
                            db.commit()
                        else:
                            stats['needs_manual_review'] += 1
                            logger.warning(
                                f"Author {author.id} needs manual review: "
                                f"language={author.language}, name='{author.name}'"
                            )
                
                # Step 2: Ensure author has both EN and RU versions
                paired_author = find_paired_author_by_quotes(db, author)
                
                if not paired_author:
                    # No paired author found - create one
                    if author.language == 'en':
                        # Create RU version
                        # Try to find existing RU author with similar name
                        similar_ru = (
                            db.query(Author)
                            .filter(
                                Author.language == 'ru',
                                Author.name.ilike(f"%{author.name.split()[0] if author.name.split() else ''}%")
                            )
                            .first()
                        )
                        
                        if similar_ru:
                            # Use existing RU author
                            paired_author = similar_ru
                            logger.info(
                                f"Found existing RU author {paired_author.id} for EN author {author.id}"
                            )
                        else:
                            # Create new RU author
                            # For now, use same name (will need manual update or translation)
                            paired_author = author_repo.create(
                                name=author.name,  # Temporary - should be Russian name
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
                            # Create new EN author
                            paired_author = author_repo.create(
                                name=author.name,  # Temporary - should be English name
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
                    stats['already_complete'] += 1
                
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
        description='Fix author name encoding and ensure bilingual pairs'
    )
    parser.add_argument(
        '--min-id',
        type=int,
        default=186,
        help='Minimum author ID to process (default: 186)'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Fixing author name encoding and ensuring bilingual pairs")
    logger.info(f"Processing authors with ID >= {args.min_id}")
    logger.info("=" * 60)
    
    if not HAS_LANGDETECT:
        logger.warning("langdetect not available, using basic character detection")
    
    db = SessionLocal()
    
    try:
        stats = fix_author_encoding_and_pairs(db, min_id=args.min_id)
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total authors processed: {stats['total']}")
        logger.info(f"  Encoding fixed: {stats['encoding_fixed']}")
        logger.info(f"  EN versions created: {stats['en_created']}")
        logger.info(f"  RU versions created: {stats['ru_created']}")
        logger.info(f"  Already had pairs: {stats['already_complete']}")
        logger.info(f"  Needs manual review: {stats['needs_manual_review']}")
        logger.info("=" * 60)
        
        if stats['needs_manual_review'] > 0:
            logger.warning(
                f"{stats['needs_manual_review']} authors need manual review. "
                "Check the logs for details."
            )
        
        if stats['en_created'] > 0 or stats['ru_created'] > 0:
            logger.warning(
                f"Created {stats['en_created'] + stats['ru_created']} new author versions. "
                "These may need manual name updates (translation)."
            )
        
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

