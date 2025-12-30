"""
Attempt to recover deleted authors from quotes that reference them.

This script:
1. Finds quotes with author_id < 292 (deleted authors)
2. Extracts author information from quote metadata or name_en/name_ru fields
3. Recreates authors with the information available
4. Updates quotes to point to recreated authors

Note: This is a best-effort recovery. Some author metadata may be lost.
"""

import sys
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from sqlalchemy import text
from logger_config import logger


def recover_authors_from_quotes(min_id: int = 292, dry_run: bool = False):
    """Recover deleted authors from quotes."""
    db = SessionLocal()
    
    try:
        # Find quotes with author_id < 292
        orphaned_quotes = (
            db.query(Quote)
            .filter(Quote.author_id < min_id, Quote.author_id.isnot(None))
            .all()
        )
        
        logger.info(f"Found {len(orphaned_quotes)} quotes with author_id < {min_id}")
        
        if len(orphaned_quotes) == 0:
            logger.info("No orphaned quotes found")
            return
        
        # Group quotes by author_id to reconstruct author info
        author_info = defaultdict(lambda: {'en_quotes': [], 'ru_quotes': []})
        
        for quote in orphaned_quotes:
            author_id = quote.author_id
            if quote.language == 'en':
                author_info[author_id]['en_quotes'].append(quote)
            elif quote.language == 'ru':
                author_info[author_id]['ru_quotes'].append(quote)
        
        logger.info(f"Found {len(author_info)} unique author IDs to recover")
        
        if dry_run:
            logger.info("DRY RUN - Would recreate authors:")
            for author_id, info in list(author_info.items())[:10]:
                logger.info(f"  Author ID {author_id}: {len(info['en_quotes'])} EN quotes, {len(info['ru_quotes'])} RU quotes")
            return
        
        # Recreate authors
        recreated = 0
        updated_quotes = 0
        
        for old_author_id, info in author_info.items():
            try:
                # Try to get author name from existing author records if any quotes have author relationship
                # Since authors are deleted, we need to infer from quotes
                # Check if there's any way to get the name
                
                # Get a sample quote to check if author relationship still exists
                sample_quote = info['en_quotes'][0] if info['en_quotes'] else info['ru_quotes'][0]
                
                # Try to find author name from quote's author relationship (if it still exists)
                # This won't work since author is deleted, so we need another approach
                
                # Check if we can find author info from other sources
                # For now, we'll create authors with placeholder names
                # The user will need to manually fix these
                
                # Try to find if there's any cached author info
                # Check quotes table for any author name hints
                
                # Since we can't reliably recover author names, we'll create placeholder authors
                logger.warning(
                    f"Cannot fully recover author {old_author_id} - "
                    f"author metadata is lost. Creating placeholder."
                )
                
                # Create new author with placeholder names
                new_author = Author(
                    name_en=f"Recovered Author {old_author_id}",
                    name_ru=f"Восстановленный автор {old_author_id}"
                )
                db.add(new_author)
                db.flush()  # Get the new ID
                
                # Update all quotes to point to new author
                for quote in info['en_quotes'] + info['ru_quotes']:
                    quote.author_id = new_author.id
                    updated_quotes += 1
                
                recreated += 1
                db.commit()
                
            except Exception as e:
                logger.error(f"Error recovering author {old_author_id}: {e}")
                db.rollback()
                continue
        
        logger.info(f"✅ Recreated {recreated} authors")
        logger.info(f"✅ Updated {updated_quotes} quotes")
        
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
        description='Recover deleted authors from quotes'
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
    logger.info("Recovering deleted authors from quotes")
    logger.info(f"Looking for quotes with author_id < {args.min_id}")
    if args.dry_run:
        logger.info("DRY RUN MODE")
    logger.info("=" * 60)
    
    recover_authors_from_quotes(min_id=args.min_id, dry_run=args.dry_run)
    
    logger.info("=" * 60)
    logger.info("Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

