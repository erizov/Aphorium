"""
Ensure each author has both EN and RU versions in the authors table.

This script:
1. Finds authors that only have one language version
2. Creates the missing language version
3. Links them by analyzing quote relationships
"""

import sys
from pathlib import Path
from typing import Optional, Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from repositories.author_repository import AuthorRepository
from logger_config import logger


def find_linked_author_by_quotes(
    db,
    author: Author
) -> Optional[Author]:
    """
    Find linked author in opposite language by checking quote relationships.
    
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
        author_counts: Dict[int, int] = {}
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


def get_author_groups(db) -> Dict[str, List[Author]]:
    """
    Group authors by their base name (without language suffix).
    
    Returns:
        Dictionary mapping normalized names to lists of authors
    """
    authors = db.query(Author).all()
    groups: Dict[str, List[Author]] = {}
    
    for author in authors:
        # Normalize name for grouping (lowercase, remove extra spaces)
        normalized = author.name.lower().strip()
        if normalized not in groups:
            groups[normalized] = []
        groups[normalized].append(author)
    
    return groups


def ensure_bilingual_authors(db) -> dict:
    """
    Ensure each author has both EN and RU versions.
    
    Returns:
        Statistics dictionary
    """
    stats = {
        'total_authors': 0,
        'already_bilingual': 0,
        'created_en': 0,
        'created_ru': 0,
        'linked_by_quotes': 0,
        'linked_by_name': 0,
        'updated_names': 0
    }
    
    try:
        author_repo = AuthorRepository(db)
        all_authors = db.query(Author).all()
        stats['total_authors'] = len(all_authors)
        
        logger.info(f"Processing {stats['total_authors']} authors...")
        
        # Group authors by name to find pairs
        author_groups = get_author_groups(db)
        
        # Track which authors we've processed
        processed_ids = set()
        
        for author in all_authors:
            if author.id in processed_ids:
                continue
            
            try:
                if author.language == 'en':
                    # Check if RU version exists
                    ru_author = find_linked_author_by_quotes(db, author)
                    
                    if ru_author and ru_author.language == 'ru':
                        # RU version exists, update name fields
                        if not author.name_en:
                            author.name_en = author.name
                        if not author.name_ru:
                            author.name_ru = ru_author.name
                        if not ru_author.name_en:
                            ru_author.name_en = author.name
                        if not ru_author.name_ru:
                            ru_author.name_ru = ru_author.name
                        stats['updated_names'] += 1
                        stats['already_bilingual'] += 1
                        processed_ids.add(author.id)
                        processed_ids.add(ru_author.id)
                    else:
                        # No RU version found, create it
                        # Try to find by name similarity first
                        similar_ru = (
                            db.query(Author)
                            .filter(
                                Author.language == 'ru',
                                Author.name.ilike(f"%{author.name.split()[0] if author.name.split() else ''}%")
                            )
                            .first()
                        )
                        
                        if similar_ru:
                            # Use existing RU author
                            ru_author = similar_ru
                            stats['linked_by_name'] += 1
                        else:
                            # Create new RU author with same name (will need manual update)
                            ru_author = author_repo.create(
                                name=author.name,  # Temporary, should be updated
                                language='ru',
                                bio=author.bio,
                                wikiquote_url=author.wikiquote_url
                            )
                            stats['created_ru'] += 1
                        
                        # Update name fields
                        if not author.name_en:
                            author.name_en = author.name
                        if not author.name_ru:
                            author.name_ru = ru_author.name
                        if not ru_author.name_en:
                            ru_author.name_en = author.name
                        if not ru_author.name_ru:
                            ru_author.name_ru = ru_author.name
                        
                        processed_ids.add(author.id)
                        processed_ids.add(ru_author.id)
                
                elif author.language == 'ru':
                    # Check if EN version exists
                    en_author = find_linked_author_by_quotes(db, author)
                    
                    if en_author and en_author.language == 'en':
                        # EN version exists, update name fields
                        if not author.name_en:
                            author.name_en = en_author.name
                        if not author.name_ru:
                            author.name_ru = author.name
                        if not en_author.name_en:
                            en_author.name_en = en_author.name
                        if not en_author.name_ru:
                            en_author.name_ru = author.name
                        stats['updated_names'] += 1
                        stats['already_bilingual'] += 1
                        processed_ids.add(author.id)
                        processed_ids.add(en_author.id)
                    else:
                        # No EN version found, create it
                        similar_en = (
                            db.query(Author)
                            .filter(
                                Author.language == 'en',
                                Author.name.ilike(f"%{author.name.split()[0] if author.name.split() else ''}%")
                            )
                            .first()
                        )
                        
                        if similar_en:
                            en_author = similar_en
                            stats['linked_by_name'] += 1
                        else:
                            # Create new EN author
                            en_author = author_repo.create(
                                name=author.name,  # Temporary
                                language='en',
                                bio=author.bio,
                                wikiquote_url=author.wikiquote_url
                            )
                            stats['created_en'] += 1
                        
                        # Update name fields
                        if not author.name_en:
                            author.name_en = en_author.name
                        if not author.name_ru:
                            author.name_ru = author.name
                        if not en_author.name_en:
                            en_author.name_en = en_author.name
                        if not en_author.name_ru:
                            en_author.name_ru = author.name
                        
                        processed_ids.add(author.id)
                        processed_ids.add(en_author.id)
                
                db.commit()
                
            except Exception as e:
                logger.warning(f"Error processing author {author.id}: {e}")
                db.rollback()
                continue
        
        logger.info(f"Processing complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to ensure bilingual authors: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Ensuring all authors have both EN and RU versions")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        stats = ensure_bilingual_authors(db)
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total authors processed: {stats['total_authors']}")
        logger.info(f"  Already had both versions: {stats['already_bilingual']}")
        logger.info(f"  Created EN versions: {stats['created_en']}")
        logger.info(f"  Created RU versions: {stats['created_ru']}")
        logger.info(f"  Linked by quote relationships: {stats['linked_by_quotes']}")
        logger.info(f"  Linked by name similarity: {stats['linked_by_name']}")
        logger.info(f"  Updated name fields: {stats['updated_names']}")
        logger.info("=" * 60)
        logger.info("Note: Newly created author pairs may need manual name updates")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

