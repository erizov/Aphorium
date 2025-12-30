"""
Verify that author encoding fixes are correct.

This script checks:
1. Name encoding matches language field
2. Each author has both EN and RU rows
"""

import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
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
    elif has_cyrillic and has_latin:
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        latin_count = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        return 'ru' if cyrillic_count > latin_count else 'en'
    
    return None


def find_paired_author_by_quotes(db, author: Author) -> Optional[Author]:
    """Find paired author in opposite language."""
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
        
    except Exception:
        return None


def verify_authors(db, min_id: int = 186) -> dict:
    """Verify author encoding and pairs."""
    stats = {
        'total': 0,
        'encoding_correct': 0,
        'encoding_wrong': 0,
        'has_pair': 0,
        'missing_pair': 0,
        'issues': []
    }
    
    all_authors = db.query(Author).filter(Author.id >= min_id).order_by(Author.id).all()
    stats['total'] = len(all_authors)
    
    processed_ids = set()
    
    for author in all_authors:
        if author.id in processed_ids:
            continue
        
        detected_lang = detect_text_language(author.name)
        
        # Check encoding
        if detected_lang and detected_lang == author.language:
            stats['encoding_correct'] += 1
        else:
            stats['encoding_wrong'] += 1
            stats['issues'].append(
                f"Author {author.id}: language={author.language}, "
                f"name encoding={detected_lang}, name='{author.name}'"
            )
        
        # Check for pair
        paired_author = find_paired_author_by_quotes(db, author)
        if paired_author:
            stats['has_pair'] += 1
            processed_ids.add(paired_author.id)
            
            # Verify paired author encoding
            paired_detected = detect_text_language(paired_author.name)
            if not (paired_detected and paired_detected == paired_author.language):
                stats['issues'].append(
                    f"Paired author {paired_author.id}: language={paired_author.language}, "
                    f"name encoding={paired_detected}, name='{paired_author.name}'"
                )
        else:
            stats['missing_pair'] += 1
            stats['issues'].append(
                f"Author {author.id} ({author.language}): '{author.name}' - no paired author"
            )
        
        processed_ids.add(author.id)
    
    return stats


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify author encoding fixes')
    parser.add_argument(
        '--min-id',
        type=int,
        default=186,
        help='Minimum author ID to process (default: 186)'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Verifying author encoding and pairs")
    logger.info(f"Processing authors with ID >= {args.min_id}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        stats = verify_authors(db, min_id=args.min_id)
        
        logger.info("=" * 60)
        logger.info("Verification Results:")
        logger.info(f"  Total authors: {stats['total']}")
        logger.info(f"  Encoding correct: {stats['encoding_correct']}")
        logger.info(f"  Encoding wrong: {stats['encoding_wrong']}")
        logger.info(f"  Has pair: {stats['has_pair']}")
        logger.info(f"  Missing pair: {stats['missing_pair']}")
        logger.info("=" * 60)
        
        if stats['issues']:
            logger.warning(f"Found {len(stats['issues'])} issues:")
            for issue in stats['issues'][:10]:  # Show first 10
                logger.warning(f"  - {issue}")
            if len(stats['issues']) > 10:
                logger.warning(f"  ... and {len(stats['issues']) - 10} more")
        else:
            logger.info("✅ All authors have correct encoding and pairs!")
        
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

