"""
Recover deleted authors by analyzing bilingual quote groups.

This script:
1. Finds quotes with author_id < 292
2. Groups them by bilingual_group_id
3. Tries to match EN/RU quotes to infer author names
4. Recreates authors and updates quotes

Note: This is best-effort recovery. Author metadata (bio, wikiquote_url) will be lost.
"""

import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, Optional

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


def recover_authors_from_bilingual_groups(min_id: int = 292, dry_run: bool = False):
    """Recover authors by analyzing bilingual quote groups."""
    db = SessionLocal()
    
    try:
        # Find all quotes with author_id < 292
        orphaned_quotes = (
            db.query(Quote)
            .filter(Quote.author_id < min_id, Quote.author_id.isnot(None))
            .all()
        )
        
        logger.info(f"Found {len(orphaned_quotes)} quotes with author_id < {min_id}")
        
        if len(orphaned_quotes) == 0:
            logger.info("No orphaned quotes found")
            return
        
        # Group quotes by old author_id
        quotes_by_old_author = defaultdict(list)
        for quote in orphaned_quotes:
            quotes_by_old_author[quote.author_id].append(quote)
        
        logger.info(f"Found {len(quotes_by_old_author)} unique author IDs to recover")
        
        # Group quotes by bilingual_group_id to find EN/RU pairs
        quotes_by_group = defaultdict(lambda: {'en': [], 'ru': []})
        for quote in orphaned_quotes:
            if quote.bilingual_group_id:
                quotes_by_group[quote.bilingual_group_id][quote.language].append(quote)
        
        # Try to match authors by finding quotes from same author_id in same bilingual groups
        author_repo = AuthorRepository(db)
        recovered = 0
        updated_quotes = 0
        
        for old_author_id, quotes in quotes_by_old_author.items():
            try:
                # Find bilingual groups these quotes belong to
                bilingual_groups = set()
                for quote in quotes:
                    if quote.bilingual_group_id:
                        bilingual_groups.add(quote.bilingual_group_id)
                
                # Try to find matching quotes in opposite language from same groups
                # This helps us infer the author's name_en and name_ru
                en_quotes = [q for q in quotes if q.language == 'en']
                ru_quotes = [q for q in quotes if q.language == 'ru']
                
                # Check if we can find author names from existing authors in same bilingual groups
                name_en = None
                name_ru = None
                
                for group_id in bilingual_groups:
                    group_quotes = quotes_by_group[group_id]
                    
                    # Find quotes in this group that have valid authors (ID >= 292)
                    valid_en_quotes = [
                        q for q in group_quotes['en'] 
                        if q.author_id and q.author_id >= min_id and q.author
                    ]
                    valid_ru_quotes = [
                        q for q in group_quotes['ru'] 
                        if q.author_id and q.author_id >= min_id and q.author
                    ]
                    
                    # If we find valid authors in same group, use their names
                    if valid_en_quotes and not name_en:
                        author = valid_en_quotes[0].author
                        if author and author.name_en:
                            name_en = author.name_en
                    
                    if valid_ru_quotes and not name_ru:
                        author = valid_ru_quotes[0].author
                        if author and author.name_ru:
                            name_ru = author.name_ru
                
                # If we couldn't infer names, use placeholders
                if not name_en:
                    name_en = f"Recovered Author {old_author_id}"
                if not name_ru:
                    name_ru = f"Восстановленный автор {old_author_id}"
                
                logger.info(
                    f"Recovering author {old_author_id}: "
                    f"name_en='{name_en}', name_ru='{name_ru}'"
                )
                
                if not dry_run:
                    # Create new author
                    new_author = author_repo.create(
                        name_en=name_en,
                        name_ru=name_ru,
                        bio=None,
                        wikiquote_url=None
                    )
                    
                    # Update all quotes to point to new author
                    for quote in quotes:
                        quote.author_id = new_author.id
                        updated_quotes += 1
                    
                    db.commit()
                    recovered += 1
                    logger.info(
                        f"✅ Recreated author {old_author_id} as {new_author.id} "
                        f"({len(quotes)} quotes updated)"
                    )
                else:
                    logger.info(f"Would recreate author {old_author_id} with {len(quotes)} quotes")
                    recovered += 1
                
            except Exception as e:
                logger.error(f"Error recovering author {old_author_id}: {e}", exc_info=True)
                db.rollback()
                continue
        
        logger.info("=" * 60)
        logger.info(f"Recovered {recovered} authors")
        logger.info(f"Updated {updated_quotes} quotes")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error recovering authors: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Recover deleted authors from bilingual quote groups'
    )
    parser.add_argument(
        '--min-id',
        type=int,
        default=292,
        help='Minimum author ID that was kept (default: 292)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Recovering deleted authors from bilingual quote groups")
    logger.info(f"Looking for quotes with author_id < {args.min_id}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    logger.info("=" * 60)
    
    recover_authors_from_bilingual_groups(min_id=args.min_id, dry_run=args.dry_run)
    
    logger.info("=" * 60)
    logger.info("Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

