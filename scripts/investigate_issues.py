"""
Investigate two issues:
1. Why quotes don't have source_id populated
2. Why only 95 authors exist when WikiQuote may have more

Usage:
    python scripts/investigate_issues.py
"""

import sys
from pathlib import Path
from sqlalchemy import func

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Quote, Author, Source
from logger_config import logger


def investigate_issues():
    """Investigate both issues."""
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("ISSUE 1: Why quotes don't have source_id populated")
        print("=" * 60)
        
        total_quotes = db.query(Quote).count()
        quotes_with_source = db.query(Quote).filter(
            Quote.source_id.isnot(None)
        ).count()
        quotes_without_source = total_quotes - quotes_with_source
        
        print(f"Total quotes: {total_quotes:,}")
        print(f"Quotes with source_id: {quotes_with_source:,}")
        print(f"Quotes without source_id: {quotes_without_source:,}")
        print(f"Percentage with source: {quotes_with_source/total_quotes*100:.2f}%")
        
        # Check how quotes were created
        quotes_with_author = db.query(Quote).filter(
            Quote.author_id.isnot(None)
        ).count()
        quotes_without_author = total_quotes - quotes_with_author
        
        print(f"\nQuotes with author_id: {quotes_with_author:,}")
        print(f"Quotes without author_id: {quotes_without_author:,}")
        
        # Check sources table
        source_count = db.query(Source).count()
        print(f"\nSources in database: {source_count}")
        
        # Check quotes by language
        quotes_by_lang = (
            db.query(Quote.language, func.count(Quote.id))
            .group_by(Quote.language)
            .all()
        )
        print("\nQuotes by language:")
        for lang, count in quotes_by_lang:
            print(f"  {lang}: {count:,}")
        
        # Check if quotes with authors have sources
        quotes_with_author_and_source = (
            db.query(Quote)
            .filter(
                Quote.author_id.isnot(None),
                Quote.source_id.isnot(None)
            )
            .count()
        )
        print(f"\nQuotes with both author_id and source_id: {quotes_with_author_and_source:,}")
        
        print("\n" + "=" * 60)
        print("ISSUE 2: Why only 95 authors exist")
        print("=" * 60)
        
        author_count = db.query(Author).count()
        print(f"Total authors in database: {author_count}")
        
        # Check authors with quotes
        authors_with_quotes = (
            db.query(Author.id)
            .join(Quote, Author.id == Quote.author_id)
            .distinct()
            .count()
        )
        print(f"Authors with quotes: {authors_with_quotes}")
        
        # Check quotes without authors
        quotes_without_author = (
            db.query(Quote)
            .filter(Quote.author_id.is_(None))
            .count()
        )
        print(f"Quotes without author_id: {quotes_without_author:,}")
        
        # Sample quotes without authors
        sample_orphaned = (
            db.query(Quote)
            .filter(Quote.author_id.is_(None))
            .limit(5)
            .all()
        )
        print(f"\nSample quotes without authors (first 5):")
        for quote in sample_orphaned:
            preview = quote.text[:60] + "..." if len(quote.text) > 60 else quote.text
            print(f"  ID {quote.id} ({quote.language}): {preview}")
        
        # Check if attribute_quotes_to_authors was run
        print("\n" + "=" * 60)
        print("Analysis:")
        print("=" * 60)
        
        print("\n1. SOURCE_ID ISSUE:")
        if quotes_with_source == 0:
            print("   - No quotes have source_id")
            print("   - Possible reasons:")
            print("     * Quotes were loaded before source tracking was implemented")
            print("     * attribute_quotes_to_authors.py doesn't set source_id")
            print("     * Quotes were created without source information")
        else:
            print(f"   - {quotes_with_source:,} quotes have source_id")
        
        print("\n2. AUTHOR COUNT ISSUE:")
        print(f"   - Only {author_count} authors in database")
        print(f"   - {quotes_without_author:,} quotes don't have authors")
        print("   - Possible reasons:")
        print("     * attribute_quotes_to_authors.py only processes existing authors")
        print("     * Need to discover new authors from orphaned quotes")
        print("     * WikiQuote may have authors not yet in database")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        logger.error(f"Error investigating issues: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    investigate_issues()

