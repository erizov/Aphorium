"""
Load 20,000 bilingual quotes (40,000 total: 20k EN + 20k RU).

This script loads quotes from authors that exist in both languages
to maximize bilingual pairs.
"""

import time
from database import SessionLocal, init_db
from scrapers.batch_loader import load_parallel, get_extended_bilingual_author_list
from scrapers.matcher import TranslationMatcher
from logger_config import logger

# Extended list of bilingual authors
EXTENDED_BILINGUAL_AUTHORS = {
    "en": [
        # Classic English authors
        "William Shakespeare", "Oscar Wilde", "Mark Twain",
        "Charles Dickens", "Jane Austen", "George Orwell",
        "Virginia Woolf", "Emily Dickinson", "Robert Frost",
        "Ralph Waldo Emerson", "Henry David Thoreau",
        "Walt Whitman", "Edgar Allan Poe", "Herman Melville",
        
        # Russian authors (English WikiQuote)
        "Fyodor Dostoevsky", "Leo Tolstoy", "Anton Chekhov",
        "Alexander Pushkin", "Mikhail Bulgakov", "Ivan Turgenev",
        "Nikolai Gogol", "Vladimir Nabokov", "Boris Pasternak",
        "Anna Akhmatova", "Marina Tsvetaeva", "Joseph Brodsky",
        
        # More authors for volume
        "Friedrich Nietzsche", "Albert Einstein", "Winston Churchill",
        "Benjamin Franklin", "Thomas Jefferson", "Abraham Lincoln",
        "Martin Luther King Jr.", "Maya Angelou", "Toni Morrison",
        "Ernest Hemingway", "F. Scott Fitzgerald", "J.D. Salinger",
        "Kurt Vonnegut", "George Bernard Shaw", "Bertrand Russell",
    ],
    "ru": [
        # Russian authors
        "Александр Пушкин", "Фёдор Достоевский", "Лев Толстой",
        "Антон Чехов", "Михаил Булгаков", "Иван Тургенев",
        "Николай Гоголь", "Владимир Набоков", "Борис Пастернак",
        "Анна Ахматова", "Марина Цветаева", "Иосиф Бродский",
        "Сергей Есенин", "Владимир Маяковский", "Александр Блок",
        "Иван Бунин", "Максим Горький", "Александр Солженицын",
        
        # English authors (Russian WikiQuote)
        "Уильям Шекспир", "Оскар Уайльд", "Марк Твен",
        "Чарльз Диккенс", "Джейн Остин", "Джордж Оруэлл",
        
        # More authors
        "Фридрих Ницше", "Альберт Эйнштейн", "Уинстон Черчилль",
    ]
}


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Loading 20,000 bilingual quotes (40,000 total)")
    logger.info("=" * 60)
    
    # Initialize database
    init_db()
    
    # Load English quotes
    logger.info("\nLoading English quotes...")
    en_authors = get_extended_bilingual_author_list("en")
    en_start = time.time()
    en_stats = load_parallel(en_authors, "en", max_workers=3)
    en_time = time.time() - en_start
    
    logger.info(f"\nEnglish quotes loaded in {en_time:.2f} seconds")
    logger.info(f"  Authors: {en_stats['authors_processed']}")
    logger.info(f"  Quotes: {en_stats['quotes_created']}")
    
    # Load Russian quotes
    logger.info("\nLoading Russian quotes...")
    ru_authors = get_extended_bilingual_author_list("ru")
    ru_start = time.time()
    ru_stats = load_parallel(ru_authors, "ru", max_workers=3)
    ru_time = time.time() - ru_start
    
    logger.info(f"\nRussian quotes loaded in {ru_time:.2f} seconds")
    logger.info(f"  Authors: {ru_stats['authors_processed']}")
    logger.info(f"  Quotes: {ru_stats['quotes_created']}")
    
    # Match translations
    logger.info("\nMatching bilingual pairs...")
    db = SessionLocal()
    matcher = TranslationMatcher(db)
    match_start = time.time()
    matches = matcher.match_all_authors()
    match_time = time.time() - match_start
    db.close()
    
    logger.info(f"\nTranslation matching completed in {match_time:.2f} seconds")
    logger.info(f"  Bilingual pairs created: {matches}")
    
    # Summary
    total_quotes = en_stats['quotes_created'] + ru_stats['quotes_created']
    total_time = en_time + ru_time + match_time
    
    logger.info("\n" + "=" * 60)
    logger.info("LOADING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total quotes: {total_quotes:,}")
    logger.info(f"  English: {en_stats['quotes_created']:,}")
    logger.info(f"  Russian: {ru_stats['quotes_created']:,}")
    logger.info(f"Bilingual pairs: {matches:,}")
    logger.info(f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    logger.info("=" * 60)
    
    if total_quotes >= 20000:
        logger.info("✅ Target of 20,000+ quotes achieved!")
    else:
        logger.warning(f"⚠️  Only {total_quotes:,} quotes loaded. Target was 20,000.")


if __name__ == "__main__":
    main()

