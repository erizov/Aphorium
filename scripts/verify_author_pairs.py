"""
Verify that each author has exactly one EN and one RU row.

This script checks:
1. Each author has at most one EN row
2. Each author has at most one RU row
3. Authors are properly paired
"""

import sys
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from logger_config import logger


def find_authors_linked_by_quotes(db, author: Author) -> Set[int]:
    """Find all author IDs linked to this author through quote relationships."""
    linked_ids = set()
    
    try:
        quotes = db.query(Quote).filter(Quote.author_id == author.id).all()
        if not quotes:
            return linked_ids
        
        bilingual_groups = set()
        for quote in quotes:
            if quote.bilingual_group_id:
                bilingual_groups.add(quote.bilingual_group_id)
        
        if not bilingual_groups:
            return linked_ids
        
        linked_quotes = (
            db.query(Quote)
            .filter(
                Quote.bilingual_group_id.in_(bilingual_groups),
                Quote.author_id.isnot(None)
            )
            .all()
        )
        
        for quote in linked_quotes:
            if quote.author_id and quote.author_id != author.id:
                linked_ids.add(quote.author_id)
        
    except Exception:
        pass
    
    return linked_ids


def verify_author_pairs(db, min_id: int = 0) -> dict:
    """Verify that each author has exactly one EN and one RU row."""
    stats = {
        'total': 0,
        'en_only': 0,
        'ru_only': 0,
        'has_both': 0,
        'multiple_en': 0,
        'multiple_ru': 0,
        'issues': []
    }
    
    all_authors = db.query(Author).filter(Author.id >= min_id).all()
    stats['total'] = len(all_authors)
    
    # Group authors by quote relationships
    author_groups = defaultdict(set)
    for author in all_authors:
        linked_ids = find_authors_linked_by_quotes(db, author)
        if linked_ids:
            # Create a group key
            group_key = tuple(sorted([author.id] + list(linked_ids)))
            author_groups[group_key].add(author.id)
            for linked_id in linked_ids:
                author_groups[group_key].add(linked_id)
        else:
            # Author with no links - standalone
            author_groups[(author.id,)].add(author.id)
    
    processed_ids = set()
    
    for group_key, author_ids in author_groups.items():
        authors = [a for a in all_authors if a.id in author_ids and a.id not in processed_ids]
        
        if not authors:
            continue
        
        # Group by language
        by_language = defaultdict(list)
        for author in authors:
            by_language[author.language].append(author)
        
        # Check for duplicates
        if len(by_language['en']) > 1:
            stats['multiple_en'] += len(by_language['en']) - 1
            stats['issues'].append(
                f"Multiple EN authors in group: {[a.id for a in by_language['en']]}"
            )
        
        if len(by_language['ru']) > 1:
            stats['multiple_ru'] += len(by_language['ru']) - 1
            stats['issues'].append(
                f"Multiple RU authors in group: {[a.id for a in by_language['ru']]}"
            )
        
        # Check if has both
        if by_language['en'] and by_language['ru']:
            stats['has_both'] += 1
        elif by_language['en']:
            stats['en_only'] += 1
            if len(authors) == 1:  # Only report if truly standalone
                stats['issues'].append(
                    f"EN-only author {authors[0].id}: '{authors[0].name}'"
                )
        elif by_language['ru']:
            stats['ru_only'] += 1
            if len(authors) == 1:  # Only report if truly standalone
                stats['issues'].append(
                    f"RU-only author {authors[0].id}: '{authors[0].name}'"
                )
        
        processed_ids.update(author_ids)
    
    # Also check for exact name duplicates within same language
    name_groups = defaultdict(list)
    for author in all_authors:
        if author.id >= min_id:
            key = f"{author.language}:{author.name.lower().strip()}"
            name_groups[key].append(author)
    
    for key, authors in name_groups.items():
        if len(authors) > 1:
            stats['issues'].append(
                f"Exact name duplicate ({key}): {[a.id for a in authors]}"
            )
    
    return stats


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Verify that each author has exactly one EN and one RU row'
    )
    parser.add_argument(
        '--min-id',
        type=int,
        default=0,
        help='Minimum author ID to process (default: 0, all authors)'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Verifying author pairs")
    logger.info(f"Processing authors with ID >= {args.min_id}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        stats = verify_author_pairs(db, min_id=args.min_id)
        
        logger.info("=" * 60)
        logger.info("Verification Results:")
        logger.info(f"  Total authors: {stats['total']}")
        logger.info(f"  Has both EN and RU: {stats['has_both']}")
        logger.info(f"  EN only: {stats['en_only']}")
        logger.info(f"  RU only: {stats['ru_only']}")
        logger.info(f"  Multiple EN rows: {stats['multiple_en']}")
        logger.info(f"  Multiple RU rows: {stats['multiple_ru']}")
        logger.info("=" * 60)
        
        if stats['issues']:
            logger.warning(f"Found {len(stats['issues'])} issues:")
            for issue in stats['issues'][:20]:  # Show first 20
                logger.warning(f"  - {issue}")
            if len(stats['issues']) > 20:
                logger.warning(f"  ... and {len(stats['issues']) - 20} more")
        else:
            logger.info("✅ All authors have correct structure!")
        
        if stats['multiple_en'] == 0 and stats['multiple_ru'] == 0:
            logger.info("✅ No duplicate EN or RU rows found!")
        else:
            logger.warning(
                f"⚠️  Found {stats['multiple_en']} duplicate EN rows and "
                f"{stats['multiple_ru']} duplicate RU rows"
            )
        
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

