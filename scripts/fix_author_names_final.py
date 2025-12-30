"""
Final fix: Use correct names from paired authors or find Russian versions.

This script:
1. For RU authors with EN names: finds the EN author, then looks for 
   another RU author linked to the same EN author that has a Russian name
2. For EN authors with RU names: finds the RU author, then looks for
   another EN author linked to the same RU author that has an English name
3. Swaps names when they're clearly swapped
4. Ensures each author has both EN and RU rows
"""

import sys
from pathlib import Path
from typing import Optional, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from models import Author, Quote
from repositories.author_repository import AuthorRepository
from logger_config import logger

try:
    from langdetect import detect, LangDetectException
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


def detect_text_language(text: str) -> Optional[str]:
    """Detect language of text."""
    if not text or not text.strip():
        return None
    
    if HAS_LANGDETECT:
        try:
            lang = detect(text)
            if lang == 'en':
                return 'en'
            elif lang == 'ru':
                return 'ru'
        except LangDetectException:
            pass
    
    # Fallback: character-based detection
    has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in text)
    has_latin = any(char.isalpha() and ord(char) < 128 for char in text)
    
    if has_cyrillic and not has_latin:
        return 'ru'
    elif has_latin and not has_cyrillic:
        return 'en'
    elif has_cyrillic and has_latin:
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        latin_count = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        return 'ru' if cyrillic_count > latin_count else 'en'
    
    return None


def find_paired_author_by_quotes(db, author: Author) -> Optional[Author]:
    """Find paired author in opposite language."""
    try:
        quotes = db.query(Quote).filter(Quote.author_id == author.id).all()
        if not quotes:
            return None
        
        bilingual_groups = set()
        for quote in quotes:
            if quote.bilingual_group_id:
                bilingual_groups.add(quote.bilingual_group_id)
        
        if not bilingual_groups:
            return None
        
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
        
        author_counts = {}
        for quote in linked_quotes:
            if quote.author_id:
                author_counts[quote.author_id] = author_counts.get(quote.author_id, 0) + 1
        
        if not author_counts:
            return None
        
        most_common_author_id = max(author_counts.items(), key=lambda x: x[1])[0]
        paired_author = db.query(Author).filter(Author.id == most_common_author_id).first()
        
        if paired_author and paired_author.language == target_language:
            return paired_author
        
        return None
        
    except Exception:
        return None


def find_other_authors_linked_to_same_en_author(
    db,
    en_author: Author,
    exclude_author_id: int
) -> List[Author]:
    """Find other RU authors linked to the same EN author."""
    try:
        quotes = db.query(Quote).filter(Quote.author_id == en_author.id).all()
        if not quotes:
            return []
        
        bilingual_groups = set()
        for quote in quotes:
            if quote.bilingual_group_id:
                bilingual_groups.add(quote.bilingual_group_id)
        
        if not bilingual_groups:
            return []
        
        linked_quotes = (
            db.query(Quote)
            .filter(
                Quote.bilingual_group_id.in_(bilingual_groups),
                Quote.language == 'ru',
                Quote.author_id != exclude_author_id,
                Quote.author_id.isnot(None)
            )
            .all()
        )
        
        author_ids = set(q.author_id for q in linked_quotes if q.author_id)
        authors = db.query(Author).filter(Author.id.in_(author_ids)).all()
        
        return [a for a in authors if a.language == 'ru']
        
    except Exception:
        return []


def fix_author_names_final(db, min_id: int = 186) -> dict:
    """Final fix using correct names from linked authors."""
    stats = {
        'total': 0,
        'swapped': 0,
        'fixed_from_linked': 0,
        'en_created': 0,
        'ru_created': 0,
        'already_correct': 0,
        'needs_manual_review': 0
    }
    
    try:
        author_repo = AuthorRepository(db)
        
        all_authors = db.query(Author).filter(Author.id >= min_id).order_by(Author.id).all()
        stats['total'] = len(all_authors)
        
        logger.info(f"Processing {stats['total']} authors (ID >= {min_id})...")
        
        processed_ids = set()
        
        for author in all_authors:
            if author.id in processed_ids:
                continue
            
            try:
                detected_lang = detect_text_language(author.name)
                
                # Check if encoding matches language
                if detected_lang and detected_lang != author.language:
                    logger.warning(
                        f"Author {author.id}: language={author.language}, "
                        f"name encoding={detected_lang}, name='{author.name}'"
                    )
                    
                    # Find paired author
                    paired_author = find_paired_author_by_quotes(db, author)
                    
                    if paired_author:
                        paired_detected = detect_text_language(paired_author.name)
                        
                        # Case 1: They are swapped
                        if (detected_lang == paired_author.language and 
                            paired_detected == author.language):
                            # Swap their names
                            temp_name = author.name
                            author.name = paired_author.name
                            paired_author.name = temp_name
                            stats['swapped'] += 1
                            logger.info(
                                f"✅ Swapped: Author {author.id} ({author.language}) "
                                f"'{author.name}' <-> Author {paired_author.id} "
                                f"({paired_author.language}) '{paired_author.name}'"
                            )
                            db.commit()
                            processed_ids.add(paired_author.id)
                        # Case 2: RU author has EN name, EN author has correct EN name
                        elif (author.language == 'ru' and 
                              paired_author.language == 'en' and
                              paired_detected == 'en'):
                            # Find other RU authors linked to the same EN author
                            other_ru_authors = find_other_authors_linked_to_same_en_author(
                                db, paired_author, author.id
                            )
                            
                            # Find one with Russian name
                            correct_ru_author = None
                            for ru_auth in other_ru_authors:
                                ru_detected = detect_text_language(ru_auth.name)
                                if ru_detected == 'ru':
                                    correct_ru_author = ru_auth
                                    break
                            
                            if correct_ru_author:
                                author.name = correct_ru_author.name
                                stats['fixed_from_linked'] += 1
                                logger.info(
                                    f"✅ Fixed: Author {author.id} RU name from linked RU author "
                                    f"{correct_ru_author.id}: '{author.name}'"
                                )
                                db.commit()
                            else:
                                stats['needs_manual_review'] += 1
                                logger.warning(
                                    f"⚠️  Author {author.id} needs manual review: "
                                    f"RU author with EN name '{author.name}', "
                                    f"cannot find Russian version"
                                )
                        # Case 3: EN author has RU name, RU author has correct RU name
                        elif (author.language == 'en' and 
                              paired_author.language == 'ru' and
                              paired_detected == 'ru'):
                            # Find other EN authors linked to the same RU author
                            # (similar logic but reversed)
                            quotes = db.query(Quote).filter(Quote.author_id == paired_author.id).all()
                            bilingual_groups = set(q.bilingual_group_id for q in quotes if q.bilingual_group_id)
                            if bilingual_groups:
                                linked_quotes = (
                                    db.query(Quote)
                                    .filter(
                                        Quote.bilingual_group_id.in_(bilingual_groups),
                                        Quote.language == 'en',
                                        Quote.author_id != author.id,
                                        Quote.author_id.isnot(None)
                                    )
                                    .all()
                                )
                                en_author_ids = set(q.author_id for q in linked_quotes if q.author_id)
                                other_en_authors = db.query(Author).filter(
                                    Author.id.in_(en_author_ids),
                                    Author.language == 'en'
                                ).all()
                                
                                correct_en_author = None
                                for en_auth in other_en_authors:
                                    en_detected = detect_text_language(en_auth.name)
                                    if en_detected == 'en':
                                        correct_en_author = en_auth
                                        break
                                
                                if correct_en_author:
                                    author.name = correct_en_author.name
                                    stats['fixed_from_linked'] += 1
                                    logger.info(
                                        f"✅ Fixed: Author {author.id} EN name from linked EN author "
                                        f"{correct_en_author.id}: '{author.name}'"
                                    )
                                    db.commit()
                                else:
                                    stats['needs_manual_review'] += 1
                                    logger.warning(
                                        f"⚠️  Author {author.id} needs manual review: "
                                        f"EN author with RU name '{author.name}'"
                                    )
                            else:
                                stats['needs_manual_review'] += 1
                                logger.warning(
                                    f"⚠️  Author {author.id} needs manual review: "
                                    f"EN author with RU name '{author.name}'"
                                )
                        else:
                            stats['needs_manual_review'] += 1
                            logger.warning(
                                f"⚠️  Author {author.id} needs manual review: "
                                f"language={author.language}, name='{author.name}'"
                            )
                    else:
                        stats['needs_manual_review'] += 1
                        logger.warning(
                            f"⚠️  Author {author.id} needs manual review: "
                            f"language={author.language}, name='{author.name}' (no paired author)"
                        )
                else:
                    stats['already_correct'] += 1
                
                # Step 2: Ensure author has both EN and RU versions
                paired_author = find_paired_author_by_quotes(db, author)
                
                if not paired_author:
                    # Try by name similarity
                    target_lang = 'ru' if author.language == 'en' else 'en'
                    similar = (
                        db.query(Author)
                        .filter(
                            Author.language == target_lang,
                            Author.name.ilike(f"%{author.name.split()[0] if author.name.split() else ''}%")
                        )
                        .first()
                    )
                    if similar:
                        paired_author = similar
                
                if not paired_author:
                    # Create missing version
                    if author.language == 'en':
                        ru_name = author.name_ru if author.name_ru else author.name
                        paired_author = author_repo.create(
                            name=ru_name,
                            language='ru',
                            bio=author.bio,
                            wikiquote_url=author.wikiquote_url
                        )
                        stats['ru_created'] += 1
                        logger.info(f"Created RU author {paired_author.id} for EN author {author.id}")
                    else:
                        en_name = author.name_en if author.name_en else author.name
                        paired_author = author_repo.create(
                            name=en_name,
                            language='en',
                            bio=author.bio,
                            wikiquote_url=author.wikiquote_url
                        )
                        stats['en_created'] += 1
                        logger.info(f"Created EN author {paired_author.id} for RU author {author.id}")
                    db.commit()
                
                # Update name_en and name_ru fields
                if author.language == 'en':
                    if not author.name_en:
                        author.name_en = author.name
                    if paired_author and not author.name_ru:
                        author.name_ru = paired_author.name
                    if paired_author and not paired_author.name_en:
                        paired_author.name_en = author.name
                    if paired_author and not paired_author.name_ru:
                        paired_author.name_ru = paired_author.name
                else:  # RU
                    if not author.name_ru:
                        author.name_ru = author.name
                    if paired_author and not author.name_en:
                        author.name_en = paired_author.name
                    if paired_author and not paired_author.name_en:
                        paired_author.name_en = paired_author.name
                    if paired_author and not paired_author.name_ru:
                        paired_author.name_ru = author.name
                
                processed_ids.add(author.id)
                if paired_author:
                    processed_ids.add(paired_author.id)
                
                db.commit()
                
            except Exception as e:
                logger.warning(f"Error processing author {author.id}: {e}")
                db.rollback()
                continue
        
        logger.info(f"Processing complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Failed to fix authors: {e}", exc_info=True)
        db.rollback()
        raise


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Final fix for author names')
    parser.add_argument('--min-id', type=int, default=186, help='Minimum author ID')
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Final fix for author name encoding")
    logger.info(f"Processing authors with ID >= {args.min_id}")
    logger.info("=" * 60)
    
    db = SessionLocal()
    
    try:
        stats = fix_author_names_final(db, min_id=args.min_id)
        
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info(f"  Total: {stats['total']}")
        logger.info(f"  Swapped: {stats['swapped']}")
        logger.info(f"  Fixed from linked: {stats['fixed_from_linked']}")
        logger.info(f"  Already correct: {stats['already_correct']}")
        logger.info(f"  EN created: {stats['en_created']}")
        logger.info(f"  RU created: {stats['ru_created']}")
        logger.info(f"  Needs review: {stats['needs_manual_review']}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

