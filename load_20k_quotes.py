"""
Load 20,000 quotes from WikiQuote (English and Russian).

Loads quotes directly from internet sources without translation.
Reports progress every 500 records.
Uses multi-layer validation to ensure only clean quotes are loaded.
"""

import argparse
import json
import os
import time
from typing import Any, Dict, List

from database import SessionLocal, init_db
from scrapers.batch_loader import (
    get_extended_bilingual_author_list,
    load_parallel,
)
from repositories.quote_repository import QuoteRepository
from logger_config import logger

# Import cleanup function for post-loading cleanup
try:
    from scripts.clean_quotes import clean_quotes
    CLEANUP_AVAILABLE = True
except ImportError:
    CLEANUP_AVAILABLE = False
    logger.warning("Cleanup script not available - skipping post-load cleanup")

PROGRESS_FILE = "data/quote_20k_loading_progress.json"
TARGET_QUOTES = 20000
PROGRESS_REPORT_INTERVAL = 500  # Report every 500 records


def load_progress() -> Dict[str, Any]:
    """Load loading progress from file."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")
    
    return {
        "en_index": 0,
        "ru_index": 0,
        "total_quotes_loaded": 0,
        "last_reported_count": 0,
        "authors_processed_en": 0,
        "authors_processed_ru": 0,
    }


def save_progress(progress: Dict[str, Any]) -> None:
    """Save progress to file."""
    os.makedirs("data", exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def get_current_quote_count() -> int:
    """Get current total quote count from database."""
    db = SessionLocal()
    try:
        from models import Quote
        count = db.query(Quote).count()
        return count
    finally:
        db.close()


def report_progress(
    current_count: int,
    target: int,
    language: str,
    authors_processed: int,
    quotes_in_batch: int
) -> None:
    """Report progress every PROGRESS_REPORT_INTERVAL records."""
    remaining = max(0, target - current_count)
    progress_pct = (current_count / target * 100) if target > 0 else 0
    
    logger.info("=" * 70)
    logger.info("📊 PROGRESS REPORT")
    logger.info("=" * 70)
    logger.info(f"Current total quotes: {current_count:,} / {target:,} ({progress_pct:.1f}%)")
    logger.info(f"Remaining: {remaining:,} quotes")
    logger.info(f"Language: {language.upper()}")
    logger.info(f"Authors processed ({language}): {authors_processed}")
    logger.info(f"Quotes in this batch: {quotes_in_batch}")
    logger.info("=" * 70)


def load_quotes_for_language(
    language: str,
    authors: List[str],
    start_index: int,
    target_remaining: int,
    progress: Dict[str, Any],
    authors_per_chunk: int = 5,
    workers: int = 3
) -> tuple:
    """
    Load quotes for a single language.
    
    Returns:
        (quotes_loaded, new_index, authors_processed)
    """
    db = SessionLocal()
    quote_repo = QuoteRepository(db)
    
    total_quotes_loaded = 0
    authors_processed = 0
    idx = start_index
    
    logger.info("=" * 70)
    logger.info(f"Loading {language.upper()} quotes")
    logger.info(f"Starting from author index: {idx}")
    logger.info(f"Target: {target_remaining:,} more quotes needed")
    logger.info("=" * 70)
    
    while idx < len(authors) and total_quotes_loaded < target_remaining:
        chunk = authors[idx:idx + authors_per_chunk]
        if not chunk:
            break
        
        logger.info(
            f"Processing {language.upper()} authors [{idx}:{idx + len(chunk)}] "
            f"({len(chunk)} authors)"
        )
        
        chunk_start = time.time()
        
        # Load quotes for this chunk
        stats = load_parallel(chunk, language, max_workers=workers)
        
        elapsed = time.time() - chunk_start
        quotes_in_chunk = stats.get("quotes_created", 0)
        
        # Get current database count
        current_count = get_current_quote_count()
        total_quotes_loaded += quotes_in_chunk
        authors_processed += stats.get("authors_processed", 0)
        
        logger.info(
            f"✅ Loaded {quotes_in_chunk} quotes in {elapsed:.1f}s "
            f"(Total: {current_count:,} quotes)"
        )
        
        # Report progress every PROGRESS_REPORT_INTERVAL records
        if current_count - progress["last_reported_count"] >= PROGRESS_REPORT_INTERVAL:
            report_progress(
                current_count,
                TARGET_QUOTES,
                language,
                authors_processed,
                quotes_in_chunk
            )
            progress["last_reported_count"] = current_count
            save_progress(progress)
        
        idx += len(chunk)
        
        # Check if we've reached target
        if current_count >= TARGET_QUOTES:
            logger.info(f"✅ Reached target of {TARGET_QUOTES:,} quotes!")
            break
        
        # Small delay between chunks
        time.sleep(0.5)
    
    db.close()
    return total_quotes_loaded, idx, authors_processed


def main() -> None:
    """Main entry point for loading 20k quotes."""
    parser = argparse.ArgumentParser(
        description="Load 20,000 quotes from WikiQuote (EN and RU)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset progress and start from beginning"
    )
    parser.add_argument(
        "--authors-per-chunk",
        type=int,
        default=5,
        help="Number of authors to process per chunk (default: 5)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3)"
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=["en", "ru", "both"],
        default="both",
        help="Language to load: en, ru, or both (default: both)"
    )
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    # Load or reset progress
    if args.reset:
        progress = {
            "en_index": 0,
            "ru_index": 0,
            "total_quotes_loaded": 0,
            "last_reported_count": 0,
            "authors_processed_en": 0,
            "authors_processed_ru": 0,
        }
        save_progress(progress)
        logger.info("Progress reset. Starting from beginning.")
    else:
        progress = load_progress()
        logger.info(
            f"Resuming: EN index {progress['en_index']}, "
            f"RU index {progress['ru_index']}, "
            f"Total loaded: {progress['total_quotes_loaded']}"
        )
    
    # Get current database count
    current_count = get_current_quote_count()
    logger.info(f"Current quotes in database: {current_count:,}")
    
    target_remaining = max(0, TARGET_QUOTES - current_count)
    
    if target_remaining == 0:
        logger.info("=" * 70)
        logger.info(f"✅ Already have {current_count:,} quotes (target: {TARGET_QUOTES:,})")
        logger.info("=" * 70)
        return
    
    logger.info(f"Target: {TARGET_QUOTES:,} quotes")
    logger.info(f"Need to load: {target_remaining:,} more quotes")
    logger.info("=" * 70)
    
    start_time = time.time()
    
    # Load English quotes
    if args.lang in ["en", "both"]:
        en_authors = get_extended_bilingual_author_list("en")
        en_remaining = target_remaining
        
        if current_count < TARGET_QUOTES and progress["en_index"] < len(en_authors):
            en_loaded, en_idx, en_authors_proc = load_quotes_for_language(
                "en",
                en_authors,
                progress["en_index"],
                en_remaining,
                progress,
                authors_per_chunk=args.authors_per_chunk,
                workers=args.workers
            )
            
            progress["en_index"] = en_idx
            progress["authors_processed_en"] += en_authors_proc
            progress["total_quotes_loaded"] += en_loaded
            
            current_count = get_current_quote_count()
            target_remaining = max(0, TARGET_QUOTES - current_count)
            save_progress(progress)
    
    # Load Russian quotes
    if args.lang in ["ru", "both"] and current_count < TARGET_QUOTES:
        ru_authors = get_extended_bilingual_author_list("ru")
        ru_remaining = target_remaining
        
        if progress["ru_index"] < len(ru_authors):
            ru_loaded, ru_idx, ru_authors_proc = load_quotes_for_language(
                "ru",
                ru_authors,
                progress["ru_index"],
                ru_remaining,
                progress,
                authors_per_chunk=args.authors_per_chunk,
                workers=args.workers
            )
            
            progress["ru_index"] = ru_idx
            progress["authors_processed_ru"] += ru_authors_proc
            progress["total_quotes_loaded"] += ru_loaded
            
            current_count = get_current_quote_count()
            save_progress(progress)
    
    # Final report
    elapsed = time.time() - start_time
    final_count = get_current_quote_count()
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("📊 FINAL REPORT")
    logger.info("=" * 70)
    logger.info(f"Total quotes in database: {final_count:,} / {TARGET_QUOTES:,}")
    logger.info(f"Time elapsed: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    logger.info(f"Authors processed (EN): {progress['authors_processed_en']}")
    logger.info(f"Authors processed (RU): {progress['authors_processed_ru']}")
    logger.info(f"Total quotes loaded this run: {progress['total_quotes_loaded']}")
    logger.info("=" * 70)
    
    # Post-load cleanup
    if CLEANUP_AVAILABLE and final_count > 0:
        logger.info("Running post-load cleanup...")
        clean_quotes()
        final_count_after_cleanup = get_current_quote_count()
        logger.info(
            f"After cleanup: {final_count_after_cleanup:,} quotes "
            f"({final_count - final_count_after_cleanup:,} removed)"
        )
    
    if final_count >= TARGET_QUOTES:
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ SUCCESS: Reached target of 20,000 quotes!")
        logger.info("=" * 70)
    else:
        remaining = TARGET_QUOTES - final_count
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"⚠️  Still need {remaining:,} more quotes to reach target")
        logger.info("Run again to continue loading")
        logger.info("=" * 70)


if __name__ == "__main__":
    main()

