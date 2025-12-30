"""
Verify and fix author names to ensure correct language encoding.

EN authors should have English names, RU authors should have Russian names.
This script detects and fixes mismatches.
"""

import sys
from pathlib import Path
from typing import Optional, Tuple

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
    # Russian uses Cyrillic characters
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
    has_latin = any(char.isalpha() and ord(char) < 128 for char in text)
    
    if has_cyrillic and not has_latin:
        return 'ru'
    elif has_latin and not has_cyrillic:
        return 'en'
    elif has_cyrillic and has_latin:
        # Mixed - count which is more
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        latin_count = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        return 'ru' if cyrillic_count > latin_count else 'en'
    
    return None


def find_correct_author_name(
    db,
    author: Author
) -> Optional[str]:
    """
    Find the correct name for an author by checking linked quotes.
    
    Args:
        db: Database session
        author: Author to check
        
    Returns:
        Correct name or None if not found
    """
    try:
        # Get quotes from this author
        quotes = db.query(Quote).filter(Quote.author_id == author.id).all()
        
        if not quotes:
            return None
        
        # Find bilingual groups
        bilingual_groups = set()
        for quote in quotes:
            if quote.bilingual_group_id:
                bilingual_groups.add(quote.bilingual_group_id)
        
        if not bilingual_groups:
            return None
        
        # Find quotes in opposite language from same groups
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
        
        # Get most common author from linked quotes
        author_counts = {}
        for quote in linked_quotes:
            if quote.author_id and quote.author:
                author_counts[quote.author.id] = quote.author
        
        if not author_counts:
            return None
        
        # Get the most common linked author
        most_common_author = list(author_counts.values())[0]
        
        # Return the name from the linked author in the correct language
        if most_common_author.language == target_language:
            return most_common_author.name
        
        return None
        
    except Exception as e:
        logger.warning(f"Error finding correct name for author {author.id}: {e}")
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
        # Get quotes from this author
        quotes = db.query(Quote).filter(Quote.author_id == author.id).all()
        
        if not quotes:
            return None
        
        # Find bilingual groups
        bilingual_groups = set()
        for quote in quotes:
            if quote.bilingual_group_id:
                bilingual_groups.add(quote.bilingual_group_id)
        
        if not bilingual_groups:
            return None
        
        # Find quotes in opposite language from same groups
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
        
        # Get most common author_id from linked quotes
        author_counts = {}
        for quote in linked_quotes:
            if quote.author_id:
                author_counts[quote.author_id] = author_counts.get(quote.author_id, 0) + 1
        
        if not author_counts:
            return None
        
        # Get author with most linked quotes
        most_common_author_id = max(author_counts.items(), key=lambda x: x[1])[0]
        paired_author = db.query(Author).filter(Author.id == most_common_author_id).first()
        
        if paired_author and paired_author.language == target_language:
            return paired_author
        
        return None
        
    except Exception as e:
        logger.warning(f"Error finding paired author for {author.id}: {e}")
        return None


def find_author_by_name_and_language(
    db,
    name: str,
    language: str,
    exclude_id: Optional[int] = None
) -> Optional[Author]:
    """
    Find author by name and language.
    
    Args:
        db: Database session
        name: Author name to search for
        language: Target language
        exclude_id: Author ID to exclude from search
        
    Returns:
        Author or None
    """
    query = db.query(Author).filter(
        Author.name == name,
        Author.language == language
    )
    
    if exclude_id:
        query = query.filter(Author.id != exclude_id)
    
    return query.first()


def verify_and_fix_author_names(db, min_id: int = 186) -> dict:
    """
    Verify and fix author names to match their language.
    
    Returns:
        Statistics dictionary
    """
    stats = {
        'total': 0,
        'correct': 0,
        'fixed': 0,
        'needs_manual_review': 0,
        'swapped_pairs': 0,
        'fixed_from_paired': 0
    }
    
    try:
        # Only process authors starting from min_id
        authors = db.query(Author).filter(Author.id >= min_id).order_by(Author.id).all()
        stats['total'] = len(authors)
        
        logger.info(f"Verifying {stats['total']} authors (ID >= {min_id})...")
        
        # First pass: identify all mismatches
        mismatches = []
        processed_ids = set()
        
        for author in authors:
            try:
                detected_lang = detect_text_language(author.name)
                
                if detected_lang is None:
                    # Can't detect, skip for now
                    continue
                
                if detected_lang != author.language:
                    # Mismatch found
                    mismatches.append((author, detected_lang))
                
            except Exception as e:
                logger.warning(f"Error checking author {author.id}: {e}")
                continue
        
        logger.info(f"Found {len(mismatches)} mismatches to fix...")
        
        # Second pass: fix mismatches
        for author, detected_lang in mismatches:
            if author.id in processed_ids:
                continue
            
            try:
                logger.info(
                    f"Fixing author {author.id}: language={author.language}, "
                    f"detected={detected_lang}, name='{author.name}'"
                )
                
                # Strategy 1: Find paired author through quotes
                paired_author = find_paired_author_by_quotes(db, author)
                
                if paired_author and paired_author.id not in processed_ids:
                    # Check if paired author also has a mismatch
                    paired_detected = detect_text_language(paired_author.name)
                    
                    if paired_detected and paired_detected != paired_author.language:
                        # Both have mismatches - check if they should be swapped
                        # If author has RU name but is EN, and paired has EN name but is RU, swap them
                        if (detected_lang == paired_author.language and 
                            paired_detected == author.language):
                            # Perfect swap case - swap their names
                            temp_name = author.name
                            author.name = paired_author.name
                            paired_author.name = temp_name
                            stats['swapped_pairs'] += 1
                            processed_ids.add(author.id)
                            processed_ids.add(paired_author.id)
                            logger.info(
                                f"Swapped names: Author {author.id} ({author.language}) "
                                f"<-> Author {paired_author.id} ({paired_author.language})"
                            )
                        elif paired_detected == author.language:
                            # Paired author has the correct name for this author
                            author.name = paired_author.name
                            stats['fixed_from_paired'] += 1
                            processed_ids.add(author.id)
                            logger.info(
                                f"Fixed author {author.id} using paired author {paired_author.id} name"
                            )
                        else:
                            # Both have wrong names but not swapped - try other strategies
                            pass
                    elif paired_detected == author.language:
                        # Paired author has the correct name for this author
                        author.name = paired_author.name
                        stats['fixed_from_paired'] += 1
                        processed_ids.add(author.id)
                        logger.info(
                            f"Fixed author {author.id} using paired author {paired_author.id} name"
                        )
                else:
                    # Strategy 2: Look for author with the detected language name in opposite language
                    # This handles cases where names are swapped
                    opposite_lang = 'ru' if author.language == 'en' else 'en'
                    swapped_author = find_author_by_name_and_language(
                        db, author.name, opposite_lang, author.id
                    )
                    
                    if swapped_author and swapped_author.id not in processed_ids:
                        # Check if swapped author also has wrong language name
                        swapped_detected = detect_text_language(swapped_author.name)
                        if swapped_detected == author.language:
                            # They are swapped - swap their names
                            temp_name = author.name
                            author.name = swapped_author.name
                            swapped_author.name = temp_name
                            stats['swapped_pairs'] += 1
                            processed_ids.add(author.id)
                            processed_ids.add(swapped_author.id)
                            logger.info(
                                f"Swapped names: Author {author.id} ({author.language}) "
                                f"<-> Author {swapped_author.id} ({swapped_author.language})"
                            )
                        else:
                            # Try to find correct name from linked quotes
                            correct_name = find_correct_author_name(db, author)
                            
                            if correct_name:
                                author.name = correct_name
                                stats['fixed'] += 1
                                processed_ids.add(author.id)
                                logger.info(
                                    f"Fixed author {author.id} from linked quotes: '{author.name}'"
                                )
                            else:
                                stats['needs_manual_review'] += 1
                                logger.warning(
                                    f"Author {author.id} needs manual review: "
                                    f"language={author.language}, name='{author.name}'"
                                )
                    else:
                        # Strategy 3: Look for any author with this name in the correct language
                        # This finds cases where the name exists but author is in wrong language
                        correct_lang_author = (
                            db.query(Author)
                            .filter(
                                Author.name == author.name,
                                Author.language == detected_lang,  # The detected language of the name
                                Author.id != author.id,
                                Author.id not in processed_ids
                            )
                            .first()
                        )
                        
                        if correct_lang_author:
                            # Found author with same name in correct language
                            # Check if that author has wrong language name
                            correct_detected = detect_text_language(correct_lang_author.name)
                            if correct_detected == author.language:
                                # They are swapped - swap their names
                                temp_name = author.name
                                author.name = correct_lang_author.name
                                correct_lang_author.name = temp_name
                                stats['swapped_pairs'] += 1
                                processed_ids.add(author.id)
                                processed_ids.add(correct_lang_author.id)
                                logger.info(
                                    f"Swapped names: Author {author.id} ({author.language}) "
                                    f"<-> Author {correct_lang_author.id} ({correct_lang_author.language})"
                                )
                            else:
                                # Try to find correct name from linked quotes
                                correct_name = find_correct_author_name(db, author)
                                
                                if correct_name:
                                    author.name = correct_name
                                    stats['fixed'] += 1
                                    processed_ids.add(author.id)
                                    logger.info(
                                        f"Fixed author {author.id} from linked quotes: '{author.name}'"
                                    )
                                else:
                                    stats['needs_manual_review'] += 1
                                    logger.warning(
                                        f"Author {author.id} needs manual review: "
                                        f"language={author.language}, name='{author.name}'"
                                    )
                        else:
                            # Strategy 4: Try to find correct name from linked quotes
                            correct_name = find_correct_author_name(db, author)
                            
                            if correct_name:
                                author.name = correct_name
                                stats['fixed'] += 1
                                processed_ids.add(author.id)
                                logger.info(
                                    f"Fixed author {author.id} from linked quotes: '{author.name}'"
                                )
                            else:
                                # Can't fix automatically
                                stats['needs_manual_review'] += 1
                                logger.warning(
                                    f"Author {author.id} needs manual review: "
                                    f"language={author.language}, name='{author.name}'"
                                )
                
                db.commit()
                
            except Exception as e:
                logger.warning(f"Error processing author {author.id}: {e}")
                db.rollback()
                continue
        
        # Count correct ones
        for author in authors:
            if author.id not in processed_ids:
                detected_lang = detect_text_language(author.name)
                if detected_lang == author.language:
                    stats['correct'] += 1
        
        logger.info(f"Verification complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to verify author names: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify and fix author name languages')
    parser.add_argument(
        '--min-id',
        type=int,
        default=186,
        help='Minimum author ID to process (default: 186)'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Verifying author names match their language")
    logger.info(f"Processing authors with ID >= {args.min_id}")
    logger.info("=" * 60)
    
    if not HAS_LANGDETECT:
        logger.warning("langdetect not available, using basic character detection")
    
    db = SessionLocal()
    
    try:
        stats = verify_and_fix_author_names(db, min_id=args.min_id)
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total authors: {stats['total']}")
        logger.info(f"  Already correct: {stats['correct']}")
        logger.info(f"  Fixed from linked quotes: {stats['fixed']}")
        logger.info(f"  Fixed from paired author: {stats['fixed_from_paired']}")
        logger.info(f"  Swapped with paired author: {stats['swapped_pairs']}")
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

