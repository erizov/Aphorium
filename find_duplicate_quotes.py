"""
Find and remove duplicate quotes from the database.

Enhanced with similarity detection and language-separate processing.
Identifies similar quotes within the same language (EN vs EN, RU vs RU)
using multiple similarity methods: exact match, token overlap, and fuzzy matching.
"""

import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

from sqlalchemy import func

from database import SessionLocal
from models import Quote
from services.quote_deduplicator import QuoteDeduplicator
from logger_config import setup_logging

# Setup logging
log_file = Path("logs") / f"deduplicate_quotes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logger = setup_logging(log_level="INFO", log_file=str(log_file))


def find_exact_duplicates(db) -> list:
    """
    Find exact duplicate quotes (legacy method for backward compatibility).
    
    Returns:
        List of duplicate groups
    """
    from sqlalchemy import func
    
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
        
        # Filter to only groups with duplicates
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
    Remove exact duplicate quotes (legacy method).
    
    Args:
        db: Database session
        dry_run: If True, only report duplicates without removing them
    
    Returns:
        Dictionary with statistics
    """
    from models import QuoteTranslation
    
    stats = {
        'duplicate_groups': 0,
        'quotes_to_remove': 0,
        'quotes_removed': 0
    }
    
    duplicates = find_exact_duplicates(db)
    stats['duplicate_groups'] = len(duplicates)
    
    logger.info(f"Found {len(duplicates)} groups of exact duplicate quotes")
    
    for dup in duplicates:
        normalized_text = dup.normalized_text
        author_id = dup.author_id
        language = dup.language
        count = dup.count
        
        # Get all quote IDs for this duplicate group
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


def deduplicate_similar_quotes(
    db,
    language: Optional[str] = None,
    dry_run: bool = True,
    token_threshold: float = 0.80,
    fuzzy_threshold: float = 0.90,
    report_csv: Optional[str] = None
) -> dict:
    """
    Deduplicate similar quotes using advanced similarity detection.
    
    Args:
        db: Database session
        language: Language to process ('en', 'ru', or None for both)
        dry_run: If True, only report without making changes
        token_threshold: Token overlap threshold (0.0-1.0)
        fuzzy_threshold: Fuzzy match threshold (0.0-1.0)
        report_csv: Optional CSV file path to save duplicate report
        
    Returns:
        Dictionary with statistics
    """
    deduplicator = QuoteDeduplicator(
        db=db,
        token_threshold=token_threshold,
        fuzzy_threshold=fuzzy_threshold
    )
    
    all_stats = {
        'total_quotes_processed': 0,
        'total_similar_pairs_found': 0,
        'total_duplicate_groups': 0,
        'total_quotes_merged': 0,
        'total_quotes_removed': 0,
        'total_translation_links_updated': 0,
        'total_bilingual_groups_merged': 0,
        'languages': {}
    }
    
    languages_to_process = []
    if language:
        languages_to_process = [language]
    else:
        # Process both languages
        languages_to_process = ['en', 'ru']
    
    # Collect similar pairs for CSV report
    similar_pairs_report = []
    
    for lang in languages_to_process:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {lang.upper()} quotes...")
        logger.info(f"{'='*60}")
        
        # Find similar pairs for reporting
        similar_pairs = deduplicator.find_similar_quotes(lang)
        
        # Add to report
        for quote1, quote2, score, method in similar_pairs:
            similar_pairs_report.append({
                'language': lang,
                'quote1_id': quote1.id,
                'quote1_text': quote1.text[:200],
                'quote2_id': quote2.id,
                'quote2_text': quote2.text[:200],
                'similarity_score': f"{score:.3f}",
                'method': method
            })
        
        # Deduplicate
        stats = deduplicator.deduplicate_by_language(lang, dry_run=dry_run)
        all_stats['languages'][lang] = stats
        
        # Aggregate statistics
        all_stats['total_quotes_processed'] += stats['quotes_processed']
        all_stats['total_similar_pairs_found'] += stats['similar_pairs_found']
        all_stats['total_duplicate_groups'] += stats['duplicate_groups']
        all_stats['total_quotes_merged'] += stats['quotes_merged']
        all_stats['total_quotes_removed'] += stats['quotes_removed']
        all_stats['total_translation_links_updated'] += stats['translation_links_updated']
        all_stats['total_bilingual_groups_merged'] += stats['bilingual_groups_merged']
    
    # Save CSV report if requested
    if report_csv and similar_pairs_report:
        report_path = Path(report_csv)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'language', 'quote1_id', 'quote1_text', 'quote2_id', 'quote2_text',
                'similarity_score', 'method'
            ])
            writer.writeheader()
            writer.writerows(similar_pairs_report)
        
        logger.info(f"Duplicate report saved to: {report_csv}")
    
    return all_stats


def print_statistics(stats: dict, dry_run: bool = False):
    """Print deduplication statistics."""
    print("\n" + "="*60)
    print("DEDUPLICATION SUMMARY")
    print("="*60)
    
    if 'languages' in stats:
        # New similarity-based statistics
        print(f"\nTotal Quotes Processed: {stats['total_quotes_processed']}")
        print(f"Total Similar Pairs Found: {stats['total_similar_pairs_found']}")
        print(f"Total Duplicate Groups: {stats['total_duplicate_groups']}")
        print(f"Total Quotes Merged: {stats['total_quotes_merged']}")
        if not dry_run:
            print(f"Total Quotes Removed: {stats['total_quotes_removed']}")
            print(f"Translation Links Updated: {stats['total_translation_links_updated']}")
            print(f"Bilingual Groups Merged: {stats['total_bilingual_groups_merged']}")
        
        print("\nBy Language:")
        for lang, lang_stats in stats['languages'].items():
            print(f"\n  {lang.upper()}:")
            print(f"    Quotes Processed: {lang_stats['quotes_processed']}")
            print(f"    Similar Pairs: {lang_stats['similar_pairs_found']}")
            print(f"    Duplicate Groups: {lang_stats['duplicate_groups']}")
            print(f"    Quotes Merged: {lang_stats['quotes_merged']}")
            if not dry_run:
                print(f"    Quotes Removed: {lang_stats['quotes_removed']}")
            print(f"    Similarity Methods:")
            for method, count in lang_stats['similarity_methods'].items():
                if count > 0:
                    print(f"      {method}: {count}")
    else:
        # Legacy exact duplicate statistics
        print(f"Duplicate Groups Found: {stats['duplicate_groups']}")
        print(f"Quotes to Remove: {stats['quotes_to_remove']}")
        if not dry_run:
            print(f"Quotes Removed: {stats['quotes_removed']}")
    
    print("="*60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Find and remove duplicate quotes from the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with similarity detection (default)
  python find_duplicate_quotes.py
  
  # Execute deduplication
  python find_duplicate_quotes.py --execute
  
  # Process only English quotes
  python find_duplicate_quotes.py --language en --execute
  
  # Custom similarity thresholds
  python find_duplicate_quotes.py --token-threshold 0.85 --fuzzy-threshold 0.92
  
  # Generate CSV report
  python find_duplicate_quotes.py --report-csv duplicates_report.csv
  
  # Legacy exact duplicate mode
  python find_duplicate_quotes.py --exact-only
        """
    )
    
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually remove duplicates (default is dry-run)'
    )
    
    parser.add_argument(
        '--language',
        choices=['en', 'ru'],
        help='Process only specified language (default: both)'
    )
    
    parser.add_argument(
        '--token-threshold',
        type=float,
        default=0.80,
        help='Token overlap threshold (0.0-1.0, default: 0.80)'
    )
    
    parser.add_argument(
        '--fuzzy-threshold',
        type=float,
        default=0.90,
        help='Fuzzy match threshold (0.0-1.0, default: 0.90)'
    )
    
    parser.add_argument(
        '--report-csv',
        type=str,
        help='Save duplicate report to CSV file'
    )
    
    parser.add_argument(
        '--exact-only',
        action='store_true',
        help='Use legacy exact duplicate detection only'
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
        print("Add --execute flag to actually remove duplicates")
        print()
    else:
        print("EXECUTE MODE - Duplicates will be removed!")
        print()
    
    db = SessionLocal()
    
    try:
        if args.exact_only:
            # Legacy exact duplicate mode
            stats = remove_duplicates(db, dry_run=dry_run)
        else:
            # New similarity-based deduplication
            stats = deduplicate_similar_quotes(
                db,
                language=args.language,
                dry_run=dry_run,
                token_threshold=args.token_threshold,
                fuzzy_threshold=args.fuzzy_threshold,
                report_csv=args.report_csv
            )
        
        print_statistics(stats, dry_run=dry_run)
        
    except Exception as e:
        logger.error(f"Failed to deduplicate quotes: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
