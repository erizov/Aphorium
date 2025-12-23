"""
Script to clear and reload all quotes with strict validation.

This script:
1. Clears all existing quotes
2. Reloads quotes using extended author list
3. Uses new strict validation (no dates, places, publishing houses, etc.)
"""

import sys
import subprocess
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger_config import logger


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Clear and reload all quotes with strict validation"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm reload (required for safety)"
    )
    parser.add_argument(
        "--lang",
        choices=["en", "ru", "both"],
        default="both",
        help="Language to reload (default: both)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3)"
    )
    
    args = parser.parse_args()
    
    if not args.confirm:
        logger.error("=" * 60)
        logger.error("WARNING: This will delete ALL quotes and reload them!")
        logger.error("=" * 60)
        logger.error("To confirm, run with --confirm flag:")
        logger.error("  python scripts/reload_all_quotes.py --confirm")
        return
    
    logger.info("=" * 60)
    logger.info("Reloading All Quotes with Strict Validation")
    logger.info("=" * 60)
    
    # Step 1: Clear all quotes
    logger.info("Step 1: Clearing all existing quotes...")
    try:
        result = subprocess.run(
            [sys.executable, "scripts/clear_all_quotes.py", "--confirm"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clear quotes: {e}")
        logger.error(e.stderr)
        return
    
    # Step 2: Reload quotes
    languages = ["en", "ru"] if args.lang == "both" else [args.lang]
    
    for lang in languages:
        logger.info(f"Step 2: Reloading {lang.upper()} quotes...")
        try:
            # Use extended author list
            result = subprocess.run(
                [
                    sys.executable, "-m", "scrapers.batch_loader",
                    "--lang", lang,
                    "--mode", "bilingual",  # Will use extended list
                    "--workers", str(args.workers)
                ],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(result.stdout)
            if result.stderr:
                logger.warning(result.stderr)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to reload {lang} quotes: {e}")
            logger.error(e.stderr)
            continue
    
    logger.info("=" * 60)
    logger.info("Reload completed!")
    logger.info("=" * 60)
    
    # Step 3: Final cleanup check
    logger.info("Step 3: Running final cleanup check...")
    try:
        result = subprocess.run(
            [sys.executable, "scripts/clean_quotes.py", "--execute"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logger.warning(f"Cleanup check failed: {e}")
    
    logger.info("=" * 60)
    logger.info("All done! Database reloaded with strict validation.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

