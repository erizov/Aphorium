"""
Clean authors table: remove records with null in name_en or name_ru, fix encoding.

Usage:
    python scripts/clean_authors_table.py [--dry-run]
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from translit_service import TranslationService
from logger_config import logger

try:
    from langdetect import detect, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


def detect_text_language(text: str) -> str:
    """Detect if text is Russian (Cyrillic) or English (Latin)."""
    if not text:
        return "unknown"
    
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
    has_latin = any(char.isalpha() and ord(char) < 128 for char in text)
    
    if has_cyrillic and not has_latin:
        return "ru"
    elif has_latin and not has_cyrillic:
        return "en"
    elif has_cyrillic and has_latin:
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        latin_count = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        return "ru" if cyrillic_count > latin_count else "en"
    
    return "unknown"


def clean_authors_table(dry_run: bool = False) -> dict:
    """
    Clean authors table.
    
    Args:
        dry_run: If True, only report what would be done
        
    Returns:
        Dictionary with statistics
    """
    db = SessionLocal()
    stats = {
        "authors_checked": 0,
        "authors_deleted": 0,
        "name_ru_fixed": 0,
        "errors": 0
    }
    
    try:
        authors = db.query(Author).all()
        stats["authors_checked"] = len(authors)
        
        logger.info(f"Checking {len(authors)} authors...")
        
        translator = TranslationService(provider='google')
        
        for author in authors:
            try:
                # Check if name_en or name_ru is null
                if author.name_en is None or author.name_ru is None:
                    # Check if author has quotes
                    quote_count = db.query(Quote).filter(
                        Quote.author_id == author.id
                    ).count()
                    
                    if quote_count > 0:
                        logger.warning(
                            f"Author {author.id} has null name but {quote_count} quotes. "
                            f"Skipping deletion."
                        )
                    else:
                        if dry_run:
                            logger.info(
                                f"Would delete author {author.id}: "
                                f"name_en={author.name_en}, name_ru={author.name_ru}"
                            )
                        else:
                            db.delete(author)
                            logger.info(f"Deleted author {author.id}")
                        stats["authors_deleted"] += 1
                    continue
                
                # Fix encoding in name_ru
                if author.name_ru:
                    # Check if it's URL-encoded
                    import urllib.parse
                    if '%' in author.name_ru:
                        try:
                            # Decode URL-encoded string
                            decoded = urllib.parse.unquote(author.name_ru)
                            if decoded != author.name_ru:
                                if not dry_run:
                                    author.name_ru = decoded
                                    db.commit()
                                    logger.info(
                                        f"Author {author.id}: Decoded URL-encoded "
                                        f"name_ru to '{decoded}'"
                                    )
                                else:
                                    logger.info(
                                        f"Would decode name_ru '{author.name_ru}' "
                                        f"to '{decoded}' for author {author.id}"
                                    )
                                stats["name_ru_fixed"] += 1
                                continue
                        except Exception as e:
                            logger.debug(f"Error decoding URL for author {author.id}: {e}")
                    
                    detected = detect_text_language(author.name_ru)
                    if detected == "en":
                        # name_ru contains English, need to translate
                        logger.warning(
                            f"Author {author.id}: name_ru='{author.name_ru}' "
                            f"contains English characters"
                        )
                        
                        if not dry_run:
                            try:
                                # Try to translate to Russian
                                translated = translator.translate(
                                    author.name_ru,
                                    source_lang='en',
                                    target_lang='ru'
                                )
                                if translated:
                                    old_name = author.name_ru
                                    author.name_ru = translated
                                    db.commit()
                                    logger.info(
                                        f"Author {author.id}: Translated name_ru "
                                        f"from '{old_name}' to '{translated}'"
                                    )
                                    stats["name_ru_fixed"] += 1
                            except Exception as e:
                                logger.error(f"Error translating author {author.id}: {e}")
                                stats["errors"] += 1
                        else:
                            logger.info(
                                f"Would translate name_ru '{author.name_ru}' "
                                f"to Russian for author {author.id}"
                            )
                            stats["name_ru_fixed"] += 1
                
            except Exception as e:
                logger.error(f"Error processing author {author.id}: {e}")
                stats["errors"] += 1
                continue
        
        if not dry_run:
            db.commit()
        
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning authors: {e}")
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean authors table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Cleaning authors table")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    stats = clean_authors_table(dry_run=args.dry_run)
    
    logger.info("=" * 60)
    logger.info("Cleaning completed!")
    logger.info(f"Authors checked: {stats['authors_checked']}")
    logger.info(f"Authors deleted: {stats['authors_deleted']}")
    logger.info(f"name_ru fixed: {stats['name_ru_fixed']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

