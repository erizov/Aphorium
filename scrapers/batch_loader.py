"""
Optimized batch loader for WikiQuote data.

Implements batch inserts and parallel scraping as recommended.
Supports loading all quotes or prioritizing bilingual authors.

Usage:
    # Load all quotes
    python -m scrapers.batch_loader --lang en --mode all

    # Load only authors that exist in both languages
    python -m scrapers.batch_loader --lang en --mode bilingual

    # Load specific authors from file
    python -m scrapers.batch_loader --lang en --authors-file authors.txt
"""

import argparse
import time
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session

from database import SessionLocal, init_db
from scrapers.wikiquote_en import WikiQuoteEnScraper
from scrapers.wikiquote_ru import WikiQuoteRuScraper
from repositories.author_repository import AuthorRepository
from repositories.source_repository import SourceRepository
from repositories.quote_repository import QuoteRepository
from logger_config import logger


# Popular authors that likely exist in both languages
BILINGUAL_AUTHORS = {
    "en": [
        "William Shakespeare", "Oscar Wilde", "Mark Twain",
        "Charles Dickens", "Jane Austen", "George Orwell",
        "Fyodor Dostoevsky", "Leo Tolstoy", "Anton Chekhov",
        "Alexander Pushkin", "Mikhail Bulgakov"
    ],
    "ru": [
        "Александр Пушкин", "Фёдор Достоевский", "Лев Толстой",
        "Антон Чехов", "Михаил Булгаков", "Иван Тургенев",
        "Николай Гоголь", "Владимир Набоков", "Борис Пастернак",
        "Анна Ахматова", "Марина Цветаева"
    ]
}


def ingest_author_batch(
    author_names: List[str],
    language: str,
    db: Session,
    batch_size: int = 100
) -> dict:
    """
    Ingest multiple authors with batch inserts.

    Args:
        author_names: List of author names
        language: Language code
        db: Database session
        batch_size: Number of quotes to insert per transaction

    Returns:
        Dictionary with statistics
    """
    stats = {
        "authors_processed": 0,
        "authors_failed": 0,
        "quotes_created": 0,
        "sources_created": 0
    }

    # Initialize scraper
    if language == "en":
        scraper = WikiQuoteEnScraper()
    elif language == "ru":
        scraper = WikiQuoteRuScraper()
    else:
        raise ValueError(f"Unsupported language: {language}")

    author_repo = AuthorRepository(db)
    source_repo = SourceRepository(db)
    quote_repo = QuoteRepository(db)

    quotes_batch = []

    for author_name in author_names:
        try:
            logger.info(f"Processing {author_name} ({language})")

            # Scrape author page
            data = scraper.scrape_author_page(author_name)

            if not data["quotes"]:
                logger.warning(f"No quotes found for {author_name}")
                stats["authors_failed"] += 1
                continue

            # Create or get author
            author = author_repo.get_or_create(
                name=data["author_name"],
                language=language,
                bio=data["bio"],
                wikiquote_url=scraper.get_author_url(author_name)
            )

            # Process quotes by source
            for source_title, quotes in data["sources"].items():
                # Check if source already exists for this author
                existing_sources = source_repo.search(source_title, limit=10)
                existing_source = None
                for src in existing_sources:
                    if src.title == source_title and src.author_id == author.id:
                        existing_source = src
                        break
                
                if existing_source:
                    source = existing_source
                else:
                    # Create new source
                    source = source_repo.create(
                        title=source_title,
                        language=language,
                        author_id=author.id,
                        source_type="book"
                    )
                    stats["sources_created"] += 1

                # Add quotes to batch
                for quote_text in quotes:
                    quotes_batch.append({
                        "text": quote_text,
                        "author_id": author.id,
                        "source_id": source.id,
                        "language": language
                    })

            # Process quotes without source
            for quote_text in data["quotes"]:
                # Skip if already processed
                if quote_text not in [
                    q for quotes_list in data["sources"].values()
                    for q in quotes_list
                ]:
                    quotes_batch.append({
                        "text": quote_text,
                        "author_id": author.id,
                        "source_id": None,
                        "language": language
                    })

            # Batch insert quotes
            if len(quotes_batch) >= batch_size:
                _insert_quotes_batch(quotes_batch, quote_repo, db)
                stats["quotes_created"] += len(quotes_batch)
                quotes_batch = []

            stats["authors_processed"] += 1
            logger.info(
                f"Processed {author_name}: {len(data['quotes'])} quotes"
            )

        except Exception as e:
            logger.error(f"Failed to process {author_name}: {e}")
            stats["authors_failed"] += 1
            continue

    # Insert remaining quotes
    if quotes_batch:
        _insert_quotes_batch(quotes_batch, quote_repo, db)
        stats["quotes_created"] += len(quotes_batch)

    return stats


def _insert_quotes_batch(
    quotes_batch: List[dict],
    quote_repo: QuoteRepository,
    db: Session
) -> None:
    """Insert a batch of quotes efficiently."""
    try:
        for quote_data in quotes_batch:
            quote_repo.create(**quote_data)
        db.commit()
        logger.debug(f"Inserted batch of {len(quotes_batch)} quotes")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to insert batch: {e}")
        raise


def load_parallel(
    author_names: List[str],
    language: str,
    max_workers: int = 3
) -> dict:
    """
    Load authors in parallel with thread pool.

    Args:
        author_names: List of author names
        language: Language code
        max_workers: Maximum number of parallel workers

    Returns:
        Combined statistics
    """
    total_stats = {
        "authors_processed": 0,
        "authors_failed": 0,
        "quotes_created": 0,
        "sources_created": 0
    }

    # Split authors into chunks for parallel processing
    chunk_size = max(1, len(author_names) // max_workers)
    author_chunks = [
        author_names[i:i + chunk_size]
        for i in range(0, len(author_names), chunk_size)
    ]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for chunk in author_chunks:
            db = SessionLocal()
            future = executor.submit(
                ingest_author_batch, chunk, language, db
            )
            futures.append((future, db))

        for future, db in futures:
            try:
                stats = future.result()
                for key in total_stats:
                    total_stats[key] += stats[key]
            except Exception as e:
                logger.error(f"Parallel load error: {e}")
            finally:
                db.close()

    return total_stats


def get_bilingual_author_list(language: str) -> List[str]:
    """
    Get list of authors that likely exist in both languages.

    Args:
        language: Language code

    Returns:
        List of author names
    """
    return BILINGUAL_AUTHORS.get(language, [])


def get_extended_bilingual_author_list(language: str) -> List[str]:
    """
    Get extended list of authors for loading more quotes.

    Args:
        language: Language code

    Returns:
        List of author names
    """
    extended = {
        "en": [
            "William Shakespeare", "Oscar Wilde", "Mark Twain",
            "Charles Dickens", "Jane Austen", "George Orwell",
            "Virginia Woolf", "Emily Dickinson", "Robert Frost",
            "Ralph Waldo Emerson", "Henry David Thoreau",
            "Walt Whitman", "Edgar Allan Poe", "Herman Melville",
            "Fyodor Dostoevsky", "Leo Tolstoy", "Anton Chekhov",
            "Alexander Pushkin", "Mikhail Bulgakov", "Ivan Turgenev",
            "Nikolai Gogol", "Vladimir Nabokov", "Boris Pasternak",
            "Anna Akhmatova", "Marina Tsvetaeva", "Joseph Brodsky",
            "Friedrich Nietzsche", "Albert Einstein", "Winston Churchill",
            "Benjamin Franklin", "Thomas Jefferson", "Abraham Lincoln",
            "Martin Luther King Jr.", "Maya Angelou", "Toni Morrison",
        "Ernest Hemingway", "F. Scott Fitzgerald", "J.D. Salinger",
        "Kurt Vonnegut", "George Bernard Shaw", "Bertrand Russell",
        "Voltaire", "Jean-Jacques Rousseau", "Immanuel Kant",
        "Plato", "Aristotle", "Socrates", "Confucius",
        "Rumi", "Khalil Gibran", "Pablo Neruda",
        "Gabriel García Márquez", "Jorge Luis Borges",
        "Franz Kafka", "Marcel Proust", "James Joyce",
        "T.S. Eliot", "W.B. Yeats", "William Blake",
        "John Keats", "Percy Bysshe Shelley", "Lord Byron",
        "Emily Brontë", "Charlotte Brontë", "Thomas Hardy",
        "D.H. Lawrence", "Aldous Huxley", "Ray Bradbury",
        "Isaac Asimov", "Arthur C. Clarke", "J.R.R. Tolkien",
        "C.S. Lewis", "J.K. Rowling", "Neil Gaiman",
        "Maya Angelou", "Langston Hughes", "Zora Neale Hurston",
        "Chinua Achebe", "Salman Rushdie", "Haruki Murakami",
        # Additional English authors
        "William Faulkner", "John Steinbeck", "Tennessee Williams",
        "Arthur Miller", "Eugene O'Neill", "Samuel Beckett",
        "Alice Walker", "James Baldwin", "Ralph Ellison",
        "Richard Wright", "Gwendolyn Brooks", "Robert Hayden",
        "Amiri Baraka", "Nikki Giovanni", "Sylvia Plath",
        "Anne Sexton", "Adrienne Rich", "Marianne Moore",
        "Elizabeth Bishop", "Louise Glück", "Billy Collins",
        "Mary Oliver", "Wendell Berry", "Gary Snyder",
        "Allen Ginsberg", "Jack Kerouac", "Charles Bukowski",
        "Hunter S. Thompson", "Tom Wolfe", "Truman Capote",
        "Norman Mailer", "Gore Vidal", "Philip Roth",
        "Saul Bellow", "Bernard Malamud", "John Updike",
        "Don DeLillo", "Thomas Pynchon", "Cormac McCarthy",
        "David Foster Wallace", "Jonathan Franzen", "Michael Chabon",
        "Zadie Smith", "Junot Díaz", "Jhumpa Lahiri",
        "Amy Tan", "Maxine Hong Kingston", "Kazuo Ishiguro",
        "Ian McEwan", "Julian Barnes", "Martin Amis",
        "Arundhati Roy", "Vikram Seth", "Rohinton Mistry",
        "Anita Desai", "Margaret Atwood", "Alice Munro",
        "Robertson Davies", "Michael Ondaatje", "Yann Martel",
        "Leonard Cohen", "Stephen King", "Dan Brown",
        "John Grisham", "Agatha Christie", "Arthur Conan Doyle",
        "Raymond Chandler", "Dashiell Hammett", "Patricia Highsmith",
        "Gillian Flynn", "Stieg Larsson", "Jo Nesbø",
        "Henning Mankell", "Donna Tartt", "Umberto Eco",
        "Italo Calvino", "Primo Levi", "José Saramago",
        "Fernando Pessoa", "Octavio Paz", "Carlos Fuentes",
        "Isabel Allende", "Mario Vargas Llosa", "Julio Cortázar",
        "Jorge Luis Borges", "Clarice Lispector", "Paulo Coelho",
        "Machado de Assis", "Haruki Murakami",
    ],
    "ru": [
        "Александр Пушкин", "Фёдор Достоевский", "Лев Толстой",
        "Антон Чехов", "Михаил Булгаков", "Иван Тургенев",
        "Николай Гоголь", "Владимир Набоков", "Борис Пастернак",
        "Анна Ахматова", "Марина Цветаева", "Иосиф Бродский",
        "Сергей Есенин", "Владимир Маяковский", "Александр Блок",
        "Иван Бунин", "Максим Горький", "Александр Солженицын",
        "Уильям Шекспир", "Оскар Уайльд", "Марк Твен",
        "Чарльз Диккенс", "Джейн Остин", "Джордж Оруэлл",
        "Фридрих Ницше", "Альберт Эйнштейн", "Уинстон Черчилль",
        "Вольтер", "Жан-Жак Руссо", "Иммануил Кант",
        "Платон", "Аристотель", "Сократ", "Конфуций",
        "Руми", "Халиль Джебран", "Пабло Неруда",
        "Габриэль Гарсиа Маркес", "Хорхе Луис Борхес",
        "Франц Кафка", "Марсель Пруст", "Джеймс Джойс",
        "Т.С. Элиот", "У.Б. Йейтс", "Уильям Блейк",
        "Джон Китс", "Перси Биши Шелли", "Лорд Байрон",
        "Эмили Бронте", "Шарлотта Бронте", "Томас Харди",
        "Д.Г. Лоуренс", "Олдос Хаксли", "Рэй Брэдбери",
        "Айзек Азимов", "Артур Кларк", "Дж.Р.Р. Толкин",
        "К.С. Льюис", "Дж.К. Роулинг", "Нил Гейман",
        "Николай Некрасов", "Афанасий Фет", "Фёдор Тютчев",
        "Валерий Брюсов", "Константин Бальмонт", "Иннокентий Анненский",
        "Велимир Хлебников", "Осип Мандельштам", "Борис Акунин",
        "Виктор Пелевин", "Людмила Улицкая", "Татьяна Толстая",
        # Additional Russian authors
        "Михаил Лермонтов", "Николай Карамзин", "Иван Крылов",
        "Александр Грибоедов", "Александр Островский", "Иван Гончаров",
        "Николай Лесков", "Алексей Толстой", "Владимир Короленко",
        "Дмитрий Мережковский", "Зинаида Гиппиус", "Андрей Белый",
        "Вячеслав Иванов", "Фёдор Сологуб", "Леонид Андреев",
        "Александр Куприн", "Алексей Ремизов", "Евгений Замятин",
        "Андрей Платонов", "Исаак Бабель", "Юрий Олеша",
        "Михаил Зощенко", "Валентин Катаев", "Константин Паустовский",
        "Владимир Обручев", "Михаил Шолохов", "Александр Фадеев",
        "Василий Гроссман", "Александр Твардовский", "Константин Симонов",
        "Василий Шукшин", "Юрий Трифонов", "Валентин Распутин",
        "Виктор Астафьев", "Василий Белов", "Юрий Бондарев",
        "Владимир Богомолов", "Григорий Бакланов", "Борис Васильев",
        "Юрий Домбровский", "Варлам Шаламов", "Владимир Войнович",
        "Александр Зиновьев", "Сергей Довлатов", "Владимир Высоцкий",
        "Булат Окуджава", "Александр Галич", "Юлий Ким",
        "Андрей Вознесенский", "Евгений Евтушенко", "Белла Ахмадулина",
        "Роберт Рождественский", "Владимир Соколов", "Давид Самойлов",
        "Арсений Тарковский", "Борис Слуцкий", "Семён Липкин",
        "Наум Коржавин", "Игорь Губерман", "Юнна Мориц",
        "Андрей Битов", "Владимир Сорокин", "Людмила Петрушевская",
        "Виктор Ерофеев", "Дмитрий Быков", "Захар Прилепин",
        "Михаил Елизаров", "Александр Проханов", "Эдуард Лимонов",
        "Александр Вампилов", "Михаил Салтыков-Щедрин", "Гавриил Державин",
        "Василий Жуковский", "Константин Батюшков", "Евгений Баратынский",
        "Александр Полежаев", "Михаил Ломоносов", "Александр Сумароков",
        "Василий Тредиаковский", "Денис Фонвизин", "Александр Радищев",
        "Николай Новиков", "Иван Дмитриев", "Василий Капнист",
        "Григорий Державин", "Александр Бестужев-Марлинский",
        "Вильгельм Кюхельбекер", "Антон Дельвиг", "Пётр Вяземский",
        "Денис Давыдов", "Александр Одоевский", "Николай Языков",
        "Алексей Хомяков", "Иван Киреевский", "Константин Аксаков",
        "Юрий Самарин", "Александр Герцен", "Николай Огарёв",
        "Александр Сухово-Кобылин", "Алексей Писемский",
        "Глеб Успенский", "Владимир Гиляровский", "Николай Гумилёв",
    ]
    }
    # Remove duplicates while preserving order
    seen = set()
    unique_list = []
    for author in extended.get(language, []):
        if author not in seen:
            seen.add(author)
            unique_list.append(author)
    return unique_list


def load_from_file(filepath: str) -> List[str]:
    """
    Load author names from a text file (one per line).

    Args:
        filepath: Path to file

    Returns:
        List of author names
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Failed to read authors file: {e}")
        return []


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch load WikiQuote data"
    )
    parser.add_argument(
        "--lang",
        required=True,
        choices=["en", "ru"],
        help="Language code"
    )
    parser.add_argument(
        "--mode",
        choices=["all", "bilingual"],
        default="bilingual",
        help="Load mode: 'all' for all authors, 'bilingual' for authors "
             "that exist in both languages"
    )
    parser.add_argument(
        "--authors-file",
        help="Path to file with author names (one per line)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel workers (default: 3)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for inserts (default: 100)"
    )

    args = parser.parse_args()

    # Initialize database
    init_db()

    # Get author list
    if args.authors_file:
        author_names = load_from_file(args.authors_file)
        logger.info(f"Loaded {len(author_names)} authors from file")
    elif args.mode == "bilingual":
        author_names = get_bilingual_author_list(args.lang)
        logger.info(
            f"Using bilingual author list: {len(author_names)} authors"
        )
    else:
        # For "all" mode, you'd need to scrape WikiQuote index pages
        # For now, use bilingual list as default
        logger.warning(
            "'all' mode not fully implemented. Using bilingual list."
        )
        author_names = get_bilingual_author_list(args.lang)

    if not author_names:
        logger.error("No authors to process")
        return

    logger.info(
        f"Starting batch load: {len(author_names)} authors, "
        f"{args.workers} workers, batch size {args.batch_size}"
    )

    start_time = time.time()

    # Load in parallel
    stats = load_parallel(
        author_names,
        args.lang,
        max_workers=args.workers
    )

    elapsed = time.time() - start_time

    logger.info("=" * 60)
    logger.info("Batch load completed!")
    logger.info(f"Time elapsed: {elapsed:.2f} seconds")
    logger.info(f"Authors processed: {stats['authors_processed']}")
    logger.info(f"Authors failed: {stats['authors_failed']}")
    logger.info(f"Quotes created: {stats['quotes_created']}")
    logger.info(f"Sources created: {stats['sources_created']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

