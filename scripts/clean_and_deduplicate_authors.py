"""
Clean and deduplicate authors table.

This script:
1. Deletes authors with NULL in name_en or name_ru (even if they have quotes)
2. Deduplicates authors using wikiquote_url as the primary key
3. Merges quotes from duplicate authors to the kept author

Usage:
    python scripts/clean_and_deduplicate_authors.py [--dry-run]
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from logger_config import logger


def clean_null_names(db, dry_run: bool = False) -> dict:
    """
    Delete authors with NULL in name_en or name_ru.
    
    Args:
        db: Database session
        dry_run: If True, only report what would be done
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "authors_checked": 0,
        "authors_deleted": 0,
        "quotes_orphaned": 0
    }
    
    try:
        # Find authors with NULL in name_en or name_ru
        authors_with_nulls = (
            db.query(Author)
            .filter(
                (Author.name_en.is_(None)) | (Author.name_ru.is_(None))
            )
            .all()
        )
        
        stats["authors_checked"] = len(authors_with_nulls)
        logger.info(f"Found {len(authors_with_nulls)} authors with NULL names")
        
        for author in authors_with_nulls:
            # Count quotes for this author
            quote_count = db.query(Quote).filter(
                Quote.author_id == author.id
            ).count()
            
            if quote_count > 0:
                stats["quotes_orphaned"] += quote_count
                logger.warning(
                    f"Author {author.id}: name_en={author.name_en}, "
                    f"name_ru={author.name_ru}, has {quote_count} quotes"
                )
            
            if dry_run:
                logger.info(
                    f"Would delete author {author.id}: "
                    f"name_en={author.name_en}, name_ru={author.name_ru}, "
                    f"quotes={quote_count}"
                )
            else:
                # Set quotes to NULL author_id
                if quote_count > 0:
                    db.query(Quote).filter(
                        Quote.author_id == author.id
                    ).update({Quote.author_id: None})
                    logger.info(
                        f"Set author_id to NULL for {quote_count} quotes "
                        f"from author {author.id}"
                    )
                
                # Delete author
                db.delete(author)
                logger.info(f"Deleted author {author.id}")
            
            stats["authors_deleted"] += 1
        
        if not dry_run:
            db.commit()
        
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning null names: {e}")
        raise


def deduplicate_by_wikiquote_url(db, dry_run: bool = False) -> dict:
    """
    Deduplicate authors using wikiquote_url as primary key.
    
    Args:
        db: Database session
        dry_run: If True, only report what would be done
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "authors_checked": 0,
        "duplicates_found": 0,
        "authors_merged": 0,
        "quotes_moved": 0,
        "authors_deleted": 0
    }
    
    try:
        # Get all authors with wikiquote_url
        authors = db.query(Author).filter(
            Author.wikiquote_url.isnot(None)
        ).all()
        
        stats["authors_checked"] = len(authors)
        logger.info(f"Checking {len(authors)} authors with wikiquote_url")
        
        # Group by wikiquote_url
        authors_by_url = defaultdict(list)
        for author in authors:
            authors_by_url[author.wikiquote_url].append(author)
        
        # Find duplicates
        duplicates = {
            url: authors_list
            for url, authors_list in authors_by_url.items()
            if len(authors_list) > 1
        }
        
        stats["duplicates_found"] = len(duplicates)
        logger.info(f"Found {len(duplicates)} duplicate URLs with {sum(len(v) for v in duplicates.values())} total authors")
        
        for url, author_list in duplicates.items():
            # Sort by ID to keep the first one
            author_list.sort(key=lambda a: a.id)
            kept_author = author_list[0]
            duplicates_to_merge = author_list[1:]
            
            logger.info(
                f"URL {url}: Keeping author {kept_author.id}, "
                f"merging {len(duplicates_to_merge)} duplicates"
            )
            
            # Merge duplicates
            for duplicate in duplicates_to_merge:
                # Count quotes to move
                quote_count = db.query(Quote).filter(
                    Quote.author_id == duplicate.id
                ).count()
                
                if quote_count > 0:
                    if dry_run:
                        logger.info(
                            f"  Would move {quote_count} quotes from author "
                            f"{duplicate.id} to {kept_author.id}"
                        )
                    else:
                        # Move quotes to kept author
                        db.query(Quote).filter(
                            Quote.author_id == duplicate.id
                        ).update({Quote.author_id: kept_author.id})
                        logger.info(
                            f"  Moved {quote_count} quotes from author "
                            f"{duplicate.id} to {kept_author.id}"
                        )
                    stats["quotes_moved"] += quote_count
                
                # Update kept author if duplicate has better data
                updated = False
                if not kept_author.name_en and duplicate.name_en:
                    kept_author.name_en = duplicate.name_en
                    updated = True
                if not kept_author.name_ru and duplicate.name_ru:
                    kept_author.name_ru = duplicate.name_ru
                    updated = True
                if not kept_author.bio and duplicate.bio:
                    kept_author.bio = duplicate.bio
                    updated = True
                
                if updated and not dry_run:
                    db.commit()
                
                # Delete duplicate
                if dry_run:
                    logger.info(f"  Would delete duplicate author {duplicate.id}")
                else:
                    db.delete(duplicate)
                    logger.info(f"  Deleted duplicate author {duplicate.id}")
                
                stats["authors_merged"] += 1
                stats["authors_deleted"] += 1
        
        if not dry_run:
            db.commit()
        
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deduplicating authors: {e}")
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean and deduplicate authors table"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done, don't make changes"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Cleaning and deduplicating authors table")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    
    db = SessionLocal()
    
    try:
        # Step 1: Clean NULL names
        logger.info("\nStep 1: Deleting authors with NULL names...")
        clean_stats = clean_null_names(db, args.dry_run)
        logger.info(f"  Checked: {clean_stats['authors_checked']}")
        logger.info(f"  Deleted: {clean_stats['authors_deleted']}")
        logger.info(f"  Quotes orphaned: {clean_stats['quotes_orphaned']}")
        
        # Step 2: Deduplicate by wikiquote_url
        logger.info("\nStep 2: Deduplicating by wikiquote_url...")
        dedup_stats = deduplicate_by_wikiquote_url(db, args.dry_run)
        logger.info(f"  Checked: {dedup_stats['authors_checked']}")
        logger.info(f"  Duplicate URLs: {dedup_stats['duplicates_found']}")
        logger.info(f"  Authors merged: {dedup_stats['authors_merged']}")
        logger.info(f"  Quotes moved: {dedup_stats['quotes_moved']}")
        logger.info(f"  Authors deleted: {dedup_stats['authors_deleted']}")
        
        logger.info("\n" + "=" * 60)
        logger.info("Cleaning and deduplication completed!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error in cleaning process: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

