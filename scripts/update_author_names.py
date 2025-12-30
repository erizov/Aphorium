"""
Update author names to populate name_en and name_ru fields.

This script:
1. For EN authors: sets name_en = name, tries to find RU version for name_ru
2. For RU authors: sets name_ru = name, tries to find EN version for name_en
3. Links authors by matching names or existing quote relationships
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from logger_config import logger


def find_linked_author_by_quotes(
    db,
    author: Author
) -> Author:
    """
    Find linked author in opposite language by checking quote relationships.
    
    If quotes from this author are linked to quotes from another author
    via bilingual_group_id, that other author is likely the translation.
    
    Args:
        db: Database session
        author: Source author
        
    Returns:
        Linked author in opposite language or None
    """
    try:
        # Get quotes from this author
        quotes = db.query(Quote).filter(Quote.author_id == author.id).all()
        
        if not quotes:
            return None
        
        # Find bilingual groups these quotes belong to
        bilingual_groups = set()
        for quote in quotes:
            if quote.bilingual_group_id:
                bilingual_groups.add(quote.bilingual_group_id)
        
        if not bilingual_groups:
            return None
        
        # Find quotes in opposite language from same bilingual groups
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
            return None
        
        # Get most common author_id from linked quotes
        author_counts = {}
        for quote in linked_quotes:
            if quote.author_id:
                author_counts[quote.author_id] = author_counts.get(quote.author_id, 0) + 1
        
        if not author_counts:
            return None
        
        # Get author with most linked quotes
        most_common_author_id = max(author_counts.items(), key=lambda x: x[1])[0]
        linked_author = db.query(Author).filter(Author.id == most_common_author_id).first()
        
        return linked_author
        
    except Exception as e:
        logger.warning(f"Error finding linked author for {author.id}: {e}")
        return None


def update_author_names(db) -> dict:
    """
    Update all authors to populate name_en and name_ru fields.
    
    Returns:
        Statistics dictionary
    """
    stats = {
        'total': 0,
        'updated_en': 0,
        'updated_ru': 0,
        'linked_by_quotes': 0,
        'linked_by_name': 0
    }
    
    try:
        authors = db.query(Author).all()
        stats['total'] = len(authors)
        
        logger.info(f"Processing {stats['total']} authors...")
        
        for author in authors:
            try:
                if author.language == 'en':
                    # English author: set name_en, find name_ru
                    if not author.name_en:
                        author.name_en = author.name
                        stats['updated_en'] += 1
                    
                    if not author.name_ru:
                        # Try to find Russian version
                        # Method 1: Find by quote relationships
                        ru_author = find_linked_author_by_quotes(db, author)
                        
                        if ru_author:
                            author.name_ru = ru_author.name
                            stats['linked_by_quotes'] += 1
                        else:
                            # Method 2: Try to find by similar name (basic matching)
                            # This is a fallback - not very reliable
                            similar_ru = (
                                db.query(Author)
                                .filter(
                                    Author.language == 'ru',
                                    Author.name.ilike(f"%{author.name.split()[0]}%")
                                )
                                .first()
                            )
                            if similar_ru:
                                author.name_ru = similar_ru.name
                                stats['linked_by_name'] += 1
                
                elif author.language == 'ru':
                    # Russian author: set name_ru, find name_en
                    if not author.name_ru:
                        author.name_ru = author.name
                        stats['updated_ru'] += 1
                    
                    if not author.name_en:
                        # Try to find English version
                        en_author = find_linked_author_by_quotes(db, author)
                        
                        if en_author:
                            author.name_en = en_author.name
                            stats['linked_by_quotes'] += 1
                        else:
                            # Method 2: Try to find by similar name
                            similar_en = (
                                db.query(Author)
                                .filter(
                                    Author.language == 'en',
                                    Author.name.ilike(f"%{author.name.split()[0]}%")
                                )
                                .first()
                            )
                            if similar_en:
                                author.name_en = similar_en.name
                                stats['linked_by_name'] += 1
                
                db.commit()
                
            except Exception as e:
                logger.warning(f"Error updating author {author.id}: {e}")
                db.rollback()
                continue
        
        logger.info(f"Update complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to update author names: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Updating author names (name_en, name_ru)")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        stats = update_author_names(db)
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total authors: {stats['total']}")
        logger.info(f"  Updated EN names: {stats['updated_en']}")
        logger.info(f"  Updated RU names: {stats['updated_ru']}")
        logger.info(f"  Linked by quotes: {stats['linked_by_quotes']}")
        logger.info(f"  Linked by name similarity: {stats['linked_by_name']}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

