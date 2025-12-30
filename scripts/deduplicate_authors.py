"""
Deduplicate author rows to ensure each author has exactly one EN and one RU row.

This script:
1. Finds duplicate authors (multiple EN or multiple RU rows for the same author)
2. Groups authors by name similarity and quote relationships
3. Merges duplicates, keeping the best row
4. Ensures each author has exactly 2 rows (one EN, one RU)
"""

import sys
from pathlib import Path
from typing import List, Dict, Set, Optional
from collections import defaultdict

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


def normalize_name(name: str) -> str:
    """Normalize author name for comparison."""
    if not name:
        return ""
    # Remove extra spaces, convert to lowercase for comparison
    return " ".join(name.strip().split()).lower()


def find_authors_linked_by_quotes(db, author: Author) -> Set[int]:
    """
    Find all author IDs linked to this author through quote relationships.
    
    Returns:
        Set of author IDs that share bilingual groups with this author
    """
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
        
        # Find all quotes in the same bilingual groups
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
        
    except Exception as e:
        logger.warning(f"Error finding linked authors for {author.id}: {e}")
    
    return linked_ids


def group_duplicate_authors(db, min_id: int = 0) -> Dict[str, List[Author]]:
    """
    Group authors that are likely duplicates.
    
    Groups by:
    1. Exact name match within same language
    2. Quote relationships (authors linked through bilingual groups)
    3. Name similarity (normalized)
    
    Returns:
        Dictionary mapping group key to list of author IDs
    """
    all_authors = db.query(Author).filter(Author.id >= min_id).all()
    
    # Group 1: Exact name match within same language
    name_groups = defaultdict(list)
    for author in all_authors:
        key = f"{author.language}:{normalize_name(author.name)}"
        name_groups[key].append(author)
    
    # Group 2: Authors linked through quotes
    quote_groups = defaultdict(set)
    for author in all_authors:
        linked_ids = find_authors_linked_by_quotes(db, author)
        if linked_ids:
            # Create a group key from sorted linked IDs
            group_key = tuple(sorted([author.id] + list(linked_ids)))
            quote_groups[group_key].add(author.id)
            for linked_id in linked_ids:
                quote_groups[group_key].add(linked_id)
    
    # Combine groups
    duplicate_groups = {}
    group_id = 0
    
    # Process name-based duplicates
    for key, authors in name_groups.items():
        if len(authors) > 1:
            # Multiple authors with same name and language
            group_key = f"name_{group_id}"
            duplicate_groups[group_key] = [a.id for a in authors]
            group_id += 1
    
    # Process quote-based groups
    for group_key, author_ids in quote_groups.items():
        if len(author_ids) > 2:  # More than 2 suggests duplicates
            # Check if they're all same language
            authors = [a for a in all_authors if a.id in author_ids]
            lang_counts = defaultdict(int)
            for a in authors:
                lang_counts[a.language] += 1
            
            # If multiple authors of same language in this group, they're duplicates
            for lang, count in lang_counts.items():
                if count > 1:
                    dup_ids = [a.id for a in authors if a.language == lang]
                    if len(dup_ids) > 1:
                        group_key_str = f"quote_{group_id}"
                        duplicate_groups[group_key_str] = dup_ids
                        group_id += 1
    
    return duplicate_groups


def select_best_author(db, author_ids: List[int]) -> int:
    """
    Select the best author from a list of duplicate author IDs.
    
    Criteria (in order):
    1. Has more quotes
    2. Has bio or wikiquote_url
    3. Has name_en and name_ru populated
    4. Lower ID (older, more established)
    
    Returns:
        Author ID to keep
    """
    authors = db.query(Author).filter(Author.id.in_(author_ids)).all()
    
    if not authors:
        return author_ids[0] if author_ids else None
    
    if len(authors) == 1:
        return authors[0].id
    
    # Score each author
    scored = []
    for author in authors:
        score = 0
        
        # Count quotes
        quote_count = db.query(Quote).filter(Quote.author_id == author.id).count()
        score += quote_count * 1000  # High weight for quote count
        
        # Has bio
        if author.bio:
            score += 100
        
        # Has wikiquote_url
        if author.wikiquote_url:
            score += 50
        
        # Has name_en and name_ru
        if author.name_en:
            score += 10
        if author.name_ru:
            score += 10
        
        # Prefer lower ID (older)
        score += (1000 - author.id) / 1000
        
        scored.append((score, author.id, author))
    
    # Sort by score (descending), then by ID (ascending)
    scored.sort(key=lambda x: (-x[0], x[1]))
    
    return scored[0][1]  # Return ID of best author


def merge_author_quotes(db, from_author_id: int, to_author_id: int):
    """
    Move all quotes from one author to another.
    
    Args:
        from_author_id: Author ID to merge from (will be deleted)
        to_author_id: Author ID to merge to (will be kept)
    """
    try:
        quotes = db.query(Quote).filter(Quote.author_id == from_author_id).all()
        for quote in quotes:
            quote.author_id = to_author_id
        db.commit()
        logger.info(
            f"Moved {len(quotes)} quotes from author {from_author_id} to {to_author_id}"
        )
    except Exception as e:
        logger.error(f"Error merging quotes: {e}")
        db.rollback()
        raise


def merge_author_data(from_author: Author, to_author: Author):
    """
    Merge data from one author into another.
    
    Args:
        from_author: Author to merge from
        to_author: Author to merge to (will be updated)
    """
    # Merge name_en and name_ru if missing
    if not to_author.name_en and from_author.name_en:
        to_author.name_en = from_author.name_en
    
    if not to_author.name_ru and from_author.name_ru:
        to_author.name_ru = from_author.name_ru
    
    # Merge bio if missing
    if not to_author.bio and from_author.bio:
        to_author.bio = from_author.bio
    
    # Merge wikiquote_url if missing
    if not to_author.wikiquote_url and from_author.wikiquote_url:
        to_author.wikiquote_url = from_author.wikiquote_url


def deduplicate_authors(db, min_id: int = 0, dry_run: bool = False) -> dict:
    """
    Deduplicate authors to ensure each has exactly one EN and one RU row.
    
    Args:
        db: Database session
        min_id: Minimum author ID to process
        dry_run: If True, don't make changes, just report
        
    Returns:
        Statistics dictionary
    """
    stats = {
        'total': 0,
        'duplicate_groups_found': 0,
        'authors_merged': 0,
        'authors_deleted': 0,
        'quotes_moved': 0,
        'errors': 0
    }
    
    try:
        # Find all authors
        all_authors = db.query(Author).filter(Author.id >= min_id).all()
        stats['total'] = len(all_authors)
        
        logger.info(f"Processing {stats['total']} authors (ID >= {min_id})...")
        
        # Find duplicate groups
        duplicate_groups = group_duplicate_authors(db, min_id=min_id)
        stats['duplicate_groups_found'] = len(duplicate_groups)
        
        logger.info(f"Found {stats['duplicate_groups_found']} duplicate groups")
        
        processed_ids = set()
        
        for group_key, author_ids in duplicate_groups.items():
            if len(author_ids) < 2:
                continue
            
            # Filter out already processed authors
            author_ids = [aid for aid in author_ids if aid not in processed_ids]
            
            if len(author_ids) < 2:
                continue
            
            try:
                # Group by language
                authors = db.query(Author).filter(Author.id.in_(author_ids)).all()
                by_language = defaultdict(list)
                for author in authors:
                    by_language[author.language].append(author)
                
                # For each language, keep only one author
                for lang, lang_authors in by_language.items():
                    if len(lang_authors) > 1:
                        # Multiple authors of same language - merge them
                        logger.warning(
                            f"Found {len(lang_authors)} {lang} authors in group {group_key}: "
                            f"{[a.id for a in lang_authors]}"
                        )
                        
                        # Select best author to keep
                        author_ids_list = [a.id for a in lang_authors]
                        best_id = select_best_author(db, author_ids_list)
                        best_author = next(a for a in lang_authors if a.id == best_id)
                        
                        # Merge others into best
                        for author in lang_authors:
                            if author.id == best_id:
                                continue
                            
                            logger.info(
                                f"Merging author {author.id} ({author.name}) "
                                f"into author {best_id} ({best_author.name})"
                            )
                            
                            if not dry_run:
                                # Merge data
                                merge_author_data(author, best_author)
                                
                                # Move quotes
                                quote_count = db.query(Quote).filter(
                                    Quote.author_id == author.id
                                ).count()
                                merge_author_quotes(db, author.id, best_id)
                                stats['quotes_moved'] += quote_count
                                
                                # Delete duplicate author
                                db.delete(author)
                                stats['authors_deleted'] += 1
                            
                            stats['authors_merged'] += 1
                            processed_ids.add(author.id)
                        
                        processed_ids.add(best_id)
                
                if not dry_run:
                    db.commit()
                    
            except Exception as e:
                logger.error(f"Error processing group {group_key}: {e}", exc_info=True)
                db.rollback()
                stats['errors'] += 1
                continue
        
        # Step 2: Ensure each author has exactly one EN and one RU row
        # Group authors by their quote relationships to find pairs
        remaining_authors = db.query(Author).filter(
            Author.id >= min_id,
            ~Author.id.in_(processed_ids)
        ).all()
        
        # Find authors that need pairs
        authors_by_quote_groups = defaultdict(set)
        for author in remaining_authors:
            linked_ids = find_authors_linked_by_quotes(db, author)
            if linked_ids:
                # Create a group
                group_key = tuple(sorted([author.id] + list(linked_ids)))
                authors_by_quote_groups[group_key].add(author.id)
                for linked_id in linked_ids:
                    authors_by_quote_groups[group_key].add(linked_id)
        
        # Check each group has exactly one EN and one RU
        for group_key, author_ids in authors_by_quote_groups.items():
            authors = db.query(Author).filter(Author.id.in_(author_ids)).all()
            by_lang = defaultdict(list)
            for author in authors:
                by_lang[author.language].append(author)
            
            # If multiple of same language, they're duplicates
            for lang, lang_authors in by_lang.items():
                if len(lang_authors) > 1:
                    logger.warning(
                        f"Found {len(lang_authors)} {lang} authors in quote group: "
                        f"{[a.id for a in lang_authors]}"
                    )
                    
                    # Select best and merge others
                    author_ids_list = [a.id for a in lang_authors]
                    best_id = select_best_author(db, author_ids_list)
                    best_author = next(a for a in lang_authors if a.id == best_id)
                    
                    for author in lang_authors:
                        if author.id == best_id:
                            continue
                        
                        logger.info(
                            f"Merging duplicate {lang} author {author.id} into {best_id}"
                        )
                        
                        if not dry_run:
                            merge_author_data(author, best_author)
                            quote_count = db.query(Quote).filter(
                                Quote.author_id == author.id
                            ).count()
                            merge_author_quotes(db, author.id, best_id)
                            stats['quotes_moved'] += quote_count
                            db.delete(author)
                            stats['authors_deleted'] += 1
                        
                        stats['authors_merged'] += 1
                        processed_ids.add(author.id)
                    
                    if not dry_run:
                        db.commit()
        
        logger.info(f"Processing complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to deduplicate authors: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Deduplicate authors to ensure exactly one EN and one RU row per author'
    )
    parser.add_argument(
        '--min-id',
        type=int,
        default=0,
        help='Minimum author ID to process (default: 0, all authors)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode - report what would be done without making changes'
    )
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Deduplicating authors")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    logger.info(f"Processing authors with ID >= {args.min_id}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        stats = deduplicate_authors(db, min_id=args.min_id, dry_run=args.dry_run)
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total authors processed: {stats['total']}")
        logger.info(f"  Duplicate groups found: {stats['duplicate_groups_found']}")
        logger.info(f"  Authors merged: {stats['authors_merged']}")
        logger.info(f"  Authors deleted: {stats['authors_deleted']}")
        logger.info(f"  Quotes moved: {stats['quotes_moved']}")
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

