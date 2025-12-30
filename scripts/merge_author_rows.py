"""
Merge duplicate author rows into single rows with both name_en and name_ru.

This script:
1. Finds EN/RU author pairs (linked through quotes)
2. Merges them into single rows with both name_en and name_ru
3. Updates all quotes to point to merged author IDs
4. Deletes duplicate author rows
5. Prepares for dropping name and language columns
"""

import sys
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from sqlalchemy import text
from logger_config import logger


def find_author_pairs(db) -> Dict[int, int]:
    """
    Find EN/RU author pairs by matching name_en and name_ru.
    
    Strategy:
    1. Match EN authors with RU authors where EN.name_en matches RU.name_ru
    2. Match EN authors with RU authors where EN.name matches RU.name_en
    3. Match through quote relationships as fallback
    
    Returns:
        Dictionary mapping: {en_author_id: ru_author_id, ...}
    """
    pairs = {}
    
    try:
        # Get all authors grouped by language
        en_authors = db.query(Author).filter(Author.language == 'en').all()
        ru_authors = db.query(Author).filter(Author.language == 'ru').all()
        
        logger.info(f"Finding pairs: {len(en_authors)} EN authors, {len(ru_authors)} RU authors")
        
        # Strategy 1: Match by name_en and name_ru
        for en_author in en_authors:
            if en_author.id in pairs.values():
                continue  # Already paired as RU side
            
            # Try to find RU author with matching name
            ru_match = None
            
            # Match: EN.name_en == RU.name_ru
            if en_author.name_en:
                ru_match = (
                    db.query(Author)
                    .filter(
                        Author.language == 'ru',
                        Author.name_ru == en_author.name_en,
                        ~Author.id.in_(pairs.values())
                    )
                    .first()
                )
            
            # Match: EN.name == RU.name_en (if name_en not set)
            if not ru_match and en_author.name:
                ru_match = (
                    db.query(Author)
                    .filter(
                        Author.language == 'ru',
                        Author.name_en == en_author.name,
                        ~Author.id.in_(pairs.values())
                    )
                    .first()
                )
            
            # Match: EN.name == RU.name (fallback)
            if not ru_match and en_author.name:
                ru_match = (
                    db.query(Author)
                    .filter(
                        Author.language == 'ru',
                        Author.name == en_author.name,
                        ~Author.id.in_(pairs.values())
                    )
                    .first()
                )
            
            if ru_match:
                pairs[en_author.id] = ru_match.id
                logger.debug(
                    f"Matched: EN {en_author.id} ('{en_author.name}') <-> "
                    f"RU {ru_match.id} ('{ru_match.name}')"
                )
        
        # Strategy 2: Match through quote relationships (for remaining authors)
        for author in en_authors + ru_authors:
            if author.id in pairs or author.id in pairs.values():
                continue
            
            quotes = db.query(Quote).filter(Quote.author_id == author.id).all()
            if not quotes:
                continue
            
            bilingual_groups = set()
            for quote in quotes:
                if quote.bilingual_group_id:
                    bilingual_groups.add(quote.bilingual_group_id)
            
            if not bilingual_groups:
                continue
            
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
                continue
            
            author_counts = {}
            for quote in linked_quotes:
                if quote.author_id:
                    author_counts[quote.author_id] = author_counts.get(quote.author_id, 0) + 1
            
            if not author_counts:
                continue
            
            most_common_id = max(author_counts.items(), key=lambda x: x[1])[0]
            linked_author = db.query(Author).filter(Author.id == most_common_id).first()
            
            if linked_author and linked_author.language == target_language:
                if author.language == 'en' and author.id not in pairs:
                    pairs[author.id] = linked_author.id
                elif linked_author.language == 'en' and linked_author.id not in pairs:
                    pairs[linked_author.id] = author.id
        
    except Exception as e:
        logger.error(f"Error finding author pairs: {e}", exc_info=True)
    
    return pairs


def merge_author_rows(db, dry_run: bool = False) -> dict:
    """
    Merge duplicate author rows into single rows.
    
    Args:
        db: Database session
        dry_run: If True, don't make changes
        
    Returns:
        Statistics dictionary
    """
    stats = {
        'total_authors': 0,
        'pairs_found': 0,
        'merged': 0,
        'quotes_updated': 0,
        'authors_deleted': 0,
        'standalone_en': 0,
        'standalone_ru': 0,
        'errors': 0
    }
    
    try:
        all_authors = db.query(Author).all()
        stats['total_authors'] = len(all_authors)
        
        logger.info(f"Processing {stats['total_authors']} authors...")
        
        # Find author pairs
        pairs = find_author_pairs(db)
        stats['pairs_found'] = len(pairs)
        logger.info(f"Found {stats['pairs_found']} author pairs")
        
        processed_ids = set()
        
        # Process pairs: merge RU into EN (keep EN author, add name_ru from RU author)
        for en_id, ru_id in pairs.items():
            if en_id in processed_ids or ru_id in processed_ids:
                continue
            
            try:
                en_author = db.query(Author).filter(Author.id == en_id).first()
                ru_author = db.query(Author).filter(Author.id == ru_id).first()
                
                if not en_author or not ru_author:
                    continue
                
                if en_author.language != 'en' or ru_author.language != 'ru':
                    continue
                
                logger.info(
                    f"Merging: EN author {en_id} ('{en_author.name}') + "
                    f"RU author {ru_id} ('{ru_author.name}')"
                )
                
                if not dry_run:
                    # Update EN author with RU name
                    if not en_author.name_ru and ru_author.name_ru:
                        en_author.name_ru = ru_author.name_ru
                    elif not en_author.name_ru and ru_author.name:
                        en_author.name_ru = ru_author.name
                    
                    # Ensure name_en is set
                    if not en_author.name_en and en_author.name:
                        en_author.name_en = en_author.name
                    
                    # Merge other fields if missing
                    if not en_author.bio and ru_author.bio:
                        en_author.bio = ru_author.bio
                    if not en_author.wikiquote_url and ru_author.wikiquote_url:
                        en_author.wikiquote_url = ru_author.wikiquote_url
                    
                    # Update all quotes from RU author to point to EN author
                    ru_quotes = db.query(Quote).filter(Quote.author_id == ru_id).all()
                    for quote in ru_quotes:
                        quote.author_id = en_id
                    stats['quotes_updated'] += len(ru_quotes)
                    
                    # Delete RU author
                    db.delete(ru_author)
                    stats['authors_deleted'] += 1
                    
                    db.commit()
                
                stats['merged'] += 1
                processed_ids.add(en_id)
                processed_ids.add(ru_id)
                
            except Exception as e:
                logger.error(f"Error merging authors {en_id} and {ru_id}: {e}", exc_info=True)
                db.rollback()
                stats['errors'] += 1
                continue
        
        # Handle standalone authors (no pairs found)
        standalone = db.query(Author).filter(~Author.id.in_(processed_ids)).all()
        
        for author in standalone:
            try:
                if author.language == 'en':
                    stats['standalone_en'] += 1
                    if not dry_run:
                        # Ensure name_en is set
                        if not author.name_en and author.name:
                            author.name_en = author.name
                        db.commit()
                elif author.language == 'ru':
                    stats['standalone_ru'] += 1
                    if not dry_run:
                        # Ensure name_ru is set
                        if not author.name_ru and author.name:
                            author.name_ru = author.name
                        db.commit()
            except Exception as e:
                logger.error(f"Error processing standalone author {author.id}: {e}")
                db.rollback()
                stats['errors'] += 1
        
        logger.info(f"Processing complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to merge authors: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Merge duplicate author rows into single rows'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode - report what would be done without making changes'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Merging duplicate author rows")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        stats = merge_author_rows(db, dry_run=args.dry_run)
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total authors: {stats['total_authors']}")
        logger.info(f"  Pairs found: {stats['pairs_found']}")
        logger.info(f"  Merged: {stats['merged']}")
        logger.info(f"  Quotes updated: {stats['quotes_updated']}")
        logger.info(f"  Authors deleted: {stats['authors_deleted']}")
        logger.info(f"  Standalone EN: {stats['standalone_en']}")
        logger.info(f"  Standalone RU: {stats['standalone_ru']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info("=" * 60)
        
        if args.dry_run:
            logger.info("This was a dry run. Run without --dry-run to apply changes.")
        
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

