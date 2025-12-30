"""
Fix author name encoding issues.

Detects and fixes cases where:
- name_en contains Russian (Cyrillic) characters
- name_ru contains only English (Latin) characters

Usage:
    python scripts/fix_author_name_encoding.py [--dry-run] [--author-id ID]
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author
from translit_service import TranslationService
from logger_config import logger

try:
    from langdetect import detect, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


def detect_text_language(text: str) -> Optional[str]:
    """Detect language of text."""
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
    
    return None


def has_cyrillic(text: str) -> bool:
    """Check if text contains Cyrillic characters."""
    if not text:
        return False
    return any('\u0400' <= char <= '\u04FF' for char in text)


def has_only_latin(text: str) -> bool:
    """Check if text contains only Latin characters."""
    if not text:
        return False
    return any(char.isalpha() and ord(char) < 128 for char in text) and \
           not has_cyrillic(text)


def fix_author_name_encoding(
    author_id: Optional[int] = None,
    dry_run: bool = False
) -> dict:
    """
    Fix author name encoding issues.
    
    Args:
        author_id: Specific author ID to fix (None for all)
        dry_run: If True, only report what would be done
        
    Returns:
        Dictionary with statistics
    """
    db = SessionLocal()
    stats = {
        "authors_checked": 0,
        "name_en_fixed": 0,
        "name_ru_fixed": 0,
        "swapped": 0,
        "errors": 0
    }
    
    try:
        # Get authors to process
        if author_id:
            authors = db.query(Author).filter(Author.id == author_id).all()
        else:
            authors = db.query(Author).all()
        
        stats["authors_checked"] = len(authors)
        logger.info(f"Checking {len(authors)} authors...")
        
        for author in authors:
            try:
                name_en_issue = False
                name_ru_issue = False
                
                # Check name_en
                if author.name_en:
                    detected_lang = detect_text_language(author.name_en)
                    if detected_lang == 'ru' or has_cyrillic(author.name_en):
                        name_en_issue = True
                        logger.warning(
                            f"Author {author.id}: name_en='{author.name_en}' "
                            f"contains Russian characters"
                        )
                
                # Check name_ru
                if author.name_ru:
                    detected_lang = detect_text_language(author.name_ru)
                    if detected_lang == 'en' or (has_only_latin(author.name_ru) and not has_cyrillic(author.name_ru)):
                        name_ru_issue = True
                        logger.warning(
                            f"Author {author.id}: name_ru='{author.name_ru}' "
                            f"contains only English characters"
                        )
                
                # Fix issues
                if name_en_issue and name_ru_issue:
                    # Both are wrong - likely swapped
                    if not dry_run:
                        temp = author.name_en
                        author.name_en = author.name_ru
                        author.name_ru = temp
                        db.commit()
                        logger.info(
                            f"Author {author.id}: Swapped name_en and name_ru"
                        )
                    else:
                        logger.info(
                            f"Would swap name_en and name_ru for author {author.id}"
                        )
                    stats["swapped"] += 1
                
                elif name_en_issue:
                    # name_en has Russian, try to translate it to English
                    original_name_en = author.name_en
                    if not dry_run:
                        try:
                            # Try to translate Russian name to English
                            translator = TranslationService(provider='google')
                            translated_name = translator.translate(
                                original_name_en,
                                source_lang='ru',
                                target_lang='en'
                            )
                            
                            if translated_name:
                                # Update name_en with translated name
                                if not author.name_ru:
                                    author.name_ru = original_name_en
                                author.name_en = translated_name
                                db.commit()
                                logger.info(
                                    f"Author {author.id}: Translated name_en "
                                    f"from '{original_name_en}' to '{translated_name}'"
                                )
                                stats["name_en_fixed"] += 1
                            else:
                                # Translation failed, move to name_ru
                                if not author.name_ru:
                                    author.name_ru = original_name_en
                                author.name_en = None
                                db.commit()
                                logger.warning(
                                    f"Author {author.id}: Translation failed, "
                                    f"moved '{original_name_en}' to name_ru, "
                                    f"cleared name_en"
                                )
                                stats["name_en_fixed"] += 1
                        except Exception as e:
                            logger.error(
                                f"Error translating author {author.id}: {e}"
                            )
                            stats["errors"] += 1
                    else:
                        # Dry run - just report
                        logger.info(
                            f"Would translate name_en '{original_name_en}' "
                            f"from Russian to English for author {author.id}"
                        )
                        stats["name_en_fixed"] += 1
                
                elif name_ru_issue:
                    # name_ru has English, but name_en might be correct
                    if author.name_en and has_cyrillic(author.name_en):
                        # name_en is also wrong (Russian), so we can't fix
                        logger.warning(
                            f"Author {author.id}: Cannot fix - both names are wrong"
                        )
                    else:
                        # Clear name_ru (it's English, should be in name_en)
                        if not dry_run:
                            if not author.name_en:
                                author.name_en = author.name_ru
                            author.name_ru = None
                            db.commit()
                            logger.info(
                                f"Author {author.id}: Moved '{author.name_en}' "
                                f"from name_ru to name_en, cleared name_ru"
                            )
                        else:
                            logger.info(
                                f"Would move '{author.name_ru}' from name_ru "
                                f"to name_en for author {author.id}"
                            )
                        stats["name_ru_fixed"] += 1
                        
            except Exception as e:
                logger.error(f"Error processing author {author.id}: {e}")
                stats["errors"] += 1
                continue
        
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in fix process: {e}")
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fix author name encoding issues"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done, don't make changes"
    )
    parser.add_argument(
        "--author-id",
        type=int,
        default=None,
        help="Fix specific author ID (default: all authors)"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Fixing author name encoding issues")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    stats = fix_author_name_encoding(
        author_id=args.author_id,
        dry_run=args.dry_run
    )
    
    logger.info("=" * 60)
    logger.info("Fix completed!")
    logger.info(f"Authors checked: {stats['authors_checked']}")
    logger.info(f"name_en fixed: {stats['name_en_fixed']}")
    logger.info(f"name_ru fixed: {stats['name_ru_fixed']}")
    logger.info(f"Swapped: {stats['swapped']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

