"""
Load quotes in resumable batches targeting 20,000 clean quotes per run.

This script:
    - Loads quotes from extended bilingual author lists (EN and RU)
    - Processes authors in small chunks so each run adds ~20k quotes
    - Tracks progress in a JSON file for safe resumability
"""

import argparse
import json
import os
import time
from typing import Any, Dict, List, Tuple

from database import SessionLocal, init_db
from scrapers.batch_loader import (
    get_extended_bilingual_author_list,
    load_parallel,
)
from scrapers.matcher import TranslationMatcher
from logger_config import logger

# Import cleanup function for post-loading cleanup
try:
    from scripts.clean_quotes import clean_quotes
    CLEANUP_AVAILABLE = True
except ImportError:
    CLEANUP_AVAILABLE = False
    logger.warning("Cleanup script not available - skipping post-load cleanup")

PROGRESS_FILE = "data/quote_loading_progress.json"
DEFAULT_TARGET_QUOTES = 20000
DEFAULT_AUTHORS_PER_CHUNK = 8


def _load_progress() -> Dict[str, Any]:
    """Load quote loading progress from file."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("en_index", 0)
                data.setdefault("ru_index", 0)
                data.setdefault("total_quotes_loaded_en", 0)
                data.setdefault("total_quotes_loaded_ru", 0)
                data.setdefault("runs_completed", 0)
                return data
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load quote progress: %s", exc)

    return {
        "en_index": 0,
        "ru_index": 0,
        "total_quotes_loaded_en": 0,
        "total_quotes_loaded_ru": 0,
        "runs_completed": 0,
    }


def _save_progress(progress: Dict[str, Any]) -> None:
    """Persist quote loading progress to file."""
    os.makedirs("data", exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def _load_language_in_chunks(
    language: str,
    authors: List[str],
    start_index: int,
    target_remaining: int,
    authors_per_chunk: int,
    workers: int,
) -> Tuple[Dict[str, int], int, int]:
    """
    Load quotes for a single language in author chunks.

    Returns stats dict, new_start_index, quotes_loaded_for_language.
    """
    total_quotes_lang = 0
    agg_stats: Dict[str, int] = {
        "authors_processed": 0,
        "authors_failed": 0,
        "quotes_created": 0,
        "sources_created": 0,
    }

    idx = start_index

    while idx < len(authors) and total_quotes_lang < target_remaining:
        chunk = authors[idx : idx + authors_per_chunk]
        if not chunk:
            break

        logger.info(
            "Loading %s authors chunk [%d:%d] (%d authors)",
            language,
            idx,
            idx + len(chunk),
            len(chunk),
        )

        chunk_start = time.time()
        stats = load_parallel(chunk, language, max_workers=workers)
        elapsed = time.time() - chunk_start

        logger.info(
            "Loaded %d quotes for %s in %.2f seconds "
            "(authors: %d processed, %d failed)",
            stats["quotes_created"],
            language,
            elapsed,
            stats["authors_processed"],
            stats["authors_failed"],
        )

        for key in agg_stats:
            agg_stats[key] += int(stats.get(key, 0))

        total_quotes_lang += int(stats.get("quotes_created", 0))
        idx += len(chunk)

        if total_quotes_lang >= target_remaining:
            break

    return agg_stats, idx, total_quotes_lang


def main() -> None:
    """Main entry point for resumable bilingual quote loading."""
    parser = argparse.ArgumentParser(
        description=(
            "Load bilingual quotes in resumable batches targeting a fixed "
            "number of quotes per run"
        )
    )
    parser.add_argument(
        "--target-quotes",
        type=int,
        default=DEFAULT_TARGET_QUOTES,
        help=(
            "Approximate number of new quotes to load per run "
            f"(default: {DEFAULT_TARGET_QUOTES})"
        ),
    )
    parser.add_argument(
        "--authors-per-chunk",
        type=int,
        default=DEFAULT_AUTHORS_PER_CHUNK,
        help=(
            "Number of authors to process per language chunk "
            f"(default: {DEFAULT_AUTHORS_PER_CHUNK})"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers for each chunk (default: 3)",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Reset progress and start from the first author in each language",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(
        "Loading quotes in resumable batches (target per run: %d)",
        args.target_quotes,
    )
    logger.info("=" * 60)

    init_db()

    if args.reset_progress:
        progress: Dict[str, Any] = {
            "en_index": 0,
            "ru_index": 0,
            "total_quotes_loaded_en": 0,
            "total_quotes_loaded_ru": 0,
            "runs_completed": 0,
        }
        _save_progress(progress)
        logger.info("Progress reset. Starting from the first author in each list.")
    else:
        progress = _load_progress()
        logger.info(
            "Resuming from EN index %d, RU index %d "
            "(EN total: %d, RU total: %d, runs: %d)",
            progress["en_index"],
            progress["ru_index"],
            progress["total_quotes_loaded_en"],
            progress["total_quotes_loaded_ru"],
            progress["runs_completed"],
        )

    en_authors = get_extended_bilingual_author_list("en")
    ru_authors = get_extended_bilingual_author_list("ru")

    if not en_authors or not ru_authors:
        logger.error("Author lists are empty. Cannot proceed.")
        return

    total_quotes_this_run = 0

    target_remaining = args.target_quotes - total_quotes_this_run
    if target_remaining > 0 and progress["en_index"] < len(en_authors):
        logger.info("Loading English quotes from index %d", progress["en_index"])
        en_stats, new_en_index, en_loaded = _load_language_in_chunks(
            "en",
            en_authors,
            progress["en_index"],
            target_remaining,
            args.authors_per_chunk,
            args.workers,
        )
        total_quotes_this_run += en_loaded
        progress["en_index"] = new_en_index
        progress["total_quotes_loaded_en"] += en_loaded
    else:
        en_stats = {
            "authors_processed": 0,
            "authors_failed": 0,
            "quotes_created": 0,
            "sources_created": 0,
        }
        logger.info("English author list exhausted or target already reached.")

    target_remaining = args.target_quotes - total_quotes_this_run
    if target_remaining > 0 and progress["ru_index"] < len(ru_authors):
        logger.info("Loading Russian quotes from index %d", progress["ru_index"])
        ru_stats, new_ru_index, ru_loaded = _load_language_in_chunks(
            "ru",
            ru_authors,
            progress["ru_index"],
            target_remaining,
            args.authors_per_chunk,
            args.workers,
        )
        total_quotes_this_run += ru_loaded
        progress["ru_index"] = new_ru_index
        progress["total_quotes_loaded_ru"] += ru_loaded
    else:
        ru_stats = {
            "authors_processed": 0,
            "authors_failed": 0,
            "quotes_created": 0,
            "sources_created": 0,
        }
        logger.info("Russian author list exhausted or target already reached.")

    progress["runs_completed"] += 1
    _save_progress(progress)

    logger.info(
        "Run complete. New quotes loaded this run: %d "
        "(EN: %d, RU: %d). Total so far EN=%d, RU=%d",
        total_quotes_this_run,
        en_stats.get("quotes_created", 0),
        ru_stats.get("quotes_created", 0),
        progress["total_quotes_loaded_en"],
        progress["total_quotes_loaded_ru"],
    )

    logger.info("Matching bilingual pairs...")
    db = SessionLocal()
    matcher = TranslationMatcher(db)
    match_start = time.time()
    matches = matcher.match_all_authors()
    match_time = time.time() - match_start
    db.close()

    logger.info(
        "Translation matching completed in %.2f seconds, pairs created: %d",
        match_time,
        matches,
    )

    # Run cleanup after loading to remove any garbage that slipped through
    if CLEANUP_AVAILABLE and total_quotes_this_run > 0:
        logger.info("Running post-load cleanup...")
        try:
            cleanup_stats = clean_quotes(dry_run=False)
            logger.info(
                "Cleanup: Deleted %d bad quotes, cleaned %d quotes",
                cleanup_stats.get("quotes_deleted", 0),
                cleanup_stats.get("quotes_updated", 0),
            )
        except Exception as e:
            logger.warning("Cleanup failed: %s", e)
    else:
        if not CLEANUP_AVAILABLE:
            logger.info("Cleanup script not available - skipping post-load cleanup")

    logger.info("=" * 60)
    logger.info(
        "RUN SUMMARY: quotes this run=%d (target=%d), total EN=%d, total RU=%d",
        total_quotes_this_run,
        args.target_quotes,
        progress["total_quotes_loaded_en"],
        progress["total_quotes_loaded_ru"],
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()


