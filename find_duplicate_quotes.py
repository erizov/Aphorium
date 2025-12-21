"""
Find and remove duplicate quotes from the database.

This script identifies duplicate quotes (same text, author, language)
and removes them, keeping only the first occurrence.
"""

from database import SessionLocal
from models import Quote, Author
from sqlalchemy import func
from logger_config import logger


def find_duplicates(db) -> list:
    """
    Find duplicate quotes in the database.
    
    Returns:
        List of duplicate groups
    """
    # Check database type
    from database import engine
    is_sqlite = 'sqlite' in str(engine.url).lower()
    
    if is_sqlite:
        # SQLite: get all quotes and group in Python
        all_quotes = db.query(Quote).all()
        quote_groups = {}
        
        for quote in all_quotes:
            normalized_text = quote.text.strip().lower()
            key = (normalized_text, quote.author_id, quote.language)
            
            if key not in quote_groups:
                quote_groups[key] = []
            quote_groups[key].append(quote.id)
        
        # Filter to only groups with duplicates and create result objects
        duplicates = []
        for key, ids in quote_groups.items():
            if len(ids) > 1:
                class DuplicateGroup:
                    def __init__(self, text, author_id, lang, count, ids):
                        self.normalized_text = text
                        self.author_id = author_id
                        self.language = lang
                        self.count = count
                        self.ids = ids
                
                duplicates.append(
                    DuplicateGroup(key[0], key[1], key[2], len(ids), ids)
                )
    else:
        # PostgreSQL: use array_agg
        try:
            duplicates = (
                db.query(
                    func.lower(func.trim(Quote.text)).label('normalized_text'),
                    Quote.author_id,
                    Quote.language,
                    func.count(Quote.id).label('count'),
                    func.array_agg(Quote.id).label('ids')
                )
                .group_by(
                    func.lower(func.trim(Quote.text)),
                    Quote.author_id,
                    Quote.language
                )
                .having(func.count(Quote.id) > 1)
                .all()
            )
        except Exception as e:
            logger.warning(f"PostgreSQL query failed, falling back to Python grouping: {e}")
            # Fallback to Python grouping
            all_quotes = db.query(Quote).all()
            quote_groups = {}
            
            for quote in all_quotes:
                normalized_text = quote.text.strip().lower()
                key = (normalized_text, quote.author_id, quote.language)
                
                if key not in quote_groups:
                    quote_groups[key] = []
                quote_groups[key].append(quote.id)
            
            duplicates = []
            for key, ids in quote_groups.items():
                if len(ids) > 1:
                    class DuplicateGroup:
                        def __init__(self, text, author_id, lang, count, ids):
                            self.normalized_text = text
                            self.author_id = author_id
                            self.language = lang
                            self.count = count
                            self.ids = ids
                    
                    duplicates.append(
                        DuplicateGroup(key[0], key[1], key[2], len(ids), ids)
                    )
    
    return duplicates


def remove_duplicates(db, dry_run: bool = True) -> dict:
    """
    Remove duplicate quotes, keeping the first occurrence.
    
    Args:
        db: Database session
        dry_run: If True, only report duplicates without removing them
    
    Returns:
        Dictionary with statistics
    """
    stats = {
        'duplicate_groups': 0,
        'quotes_to_remove': 0,
        'quotes_removed': 0
    }
    
    duplicates = find_duplicates(db)
    stats['duplicate_groups'] = len(duplicates)
    
    logger.info(f"Found {len(duplicates)} groups of duplicate quotes")
    
    for dup in duplicates:
        normalized_text = dup.normalized_text
        author_id = dup.author_id
        language = dup.language
        count = dup.count
        
        # Get all quote IDs for this duplicate group
        # Use the IDs from the duplicate group if available
        if hasattr(dup, 'ids') and isinstance(dup.ids, list):
            quote_ids = sorted(dup.ids)
        else:
            quote_ids = (
                db.query(Quote.id)
                .filter(
                    func.lower(func.trim(Quote.text)) == normalized_text,
                    Quote.author_id == author_id,
                    Quote.language == language
                )
                .order_by(Quote.id)
                .all()
            )
            quote_ids = [qid[0] if isinstance(qid, tuple) else qid.id for qid in quote_ids]
        
        # Keep the first one (lowest ID), remove the rest
        keep_id = quote_ids[0]
        remove_ids = quote_ids[1:]
        
        stats['quotes_to_remove'] += len(remove_ids)
        
        logger.info(
            f"Duplicate group: '{normalized_text[:50]}...' "
            f"(author_id={author_id}, lang={language}) - "
            f"keeping ID {keep_id}, removing {len(remove_ids)} duplicates"
        )
        
        if not dry_run:
            # Update any translations pointing to removed quotes
            from models import QuoteTranslation
            
            for remove_id in remove_ids:
                # Update translations that point to the quote we're removing
                db.query(QuoteTranslation).filter(
                    QuoteTranslation.translated_quote_id == remove_id
                ).update({
                    QuoteTranslation.translated_quote_id: keep_id
                })
                
                # Update translations from the quote we're removing
                db.query(QuoteTranslation).filter(
                    QuoteTranslation.quote_id == remove_id
                ).update({
                    QuoteTranslation.quote_id: keep_id
                })
                
                # Delete the duplicate quote
                db.query(Quote).filter(Quote.id == remove_id).delete()
                stats['quotes_removed'] += 1
            
            db.commit()
            logger.info(f"Removed {len(remove_ids)} duplicate quotes")
    
    return stats


def main():
    """Main entry point."""
    import sys
    
    dry_run = '--execute' not in sys.argv
    
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
        print("Add --execute flag to actually remove duplicates")
        print()
    else:
        print("EXECUTE MODE - Duplicates will be removed!")
        print()
    
    db = SessionLocal()
    
    try:
        stats = remove_duplicates(db, dry_run=dry_run)
        
        print("\n" + "="*60)
        print("DUPLICATE REMOVAL SUMMARY")
        print("="*60)
        print(f"Duplicate groups found: {stats['duplicate_groups']}")
        print(f"Quotes to remove: {stats['quotes_to_remove']}")
        if not dry_run:
            print(f"Quotes removed: {stats['quotes_removed']}")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Failed to remove duplicates: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

