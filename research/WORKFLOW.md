# Aphorium Workflow

## Basic Workflow

### 1. Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your database credentials

# Initialize database
python init_database.py
```

### 2. Data Ingestion

#### Ingest from WikiQuote

```bash
# Ingest English author
python -m scrapers.ingest --lang en --author "William Shakespeare"

# Ingest Russian author
python -m scrapers.ingest --lang ru --author "Александр Пушкин"

# Ingest more authors as needed
python -m scrapers.ingest --lang en --author "Oscar Wilde"
python -m scrapers.ingest --lang ru --author "Фёдор Достоевский"
```

#### Match Bilingual Pairs

After ingesting authors in both languages:

```python
from database import SessionLocal
from scrapers.matcher import TranslationMatcher

db = SessionLocal()
matcher = TranslationMatcher(db)
matcher.match_all_authors()
db.close()
```

Or create a script:

```bash
python -c "
from database import SessionLocal
from scrapers.matcher import TranslationMatcher
db = SessionLocal()
matcher = TranslationMatcher(db)
print(f'Matched {matcher.match_all_authors()} quote pairs')
db.close()
"
```

### 3. Start API Server

```bash
uvicorn api.main:app --reload
```

API will be available at `http://localhost:8000`

### 4. Use Frontend

Open `frontend/index.html` in your browser, or serve it:

```bash
cd frontend
python -m http.server 8001
```

Then open `http://localhost:8001` in your browser.

## API Usage Examples

### Search Quotes

```bash
# Search all languages
curl "http://localhost:8000/api/quotes/search?q=love&limit=10"

# Search English only
curl "http://localhost:8000/api/quotes/search?q=love&lang=en"

# Search with bilingual preference
curl "http://localhost:8000/api/quotes/search?q=love&prefer_bilingual=true"
```

### Get Quote with Translations

```bash
curl "http://localhost:8000/api/quotes/1"
```

### Get Bilingual Pairs

```bash
curl "http://localhost:8000/api/quotes/bilingual/pairs?limit=10"
```

### Search Authors

```bash
curl "http://localhost:8000/api/authors?name=Shakespeare"
```

## Testing

```bash
# Run all tests
pytest

# Run e2e tests only
pytest tests/e2e/

# Run unit tests only
pytest tests/unit/

# Run with coverage
pytest --cov=. --cov-report=html
```

## Data Enrichment Workflow

### Adding New Sources

1. Create a new scraper in `scrapers/` following the base scraper pattern
2. Implement `scrape_author_page()` method
3. Use the ingestion script to import data
4. Run translation matcher to find bilingual pairs

### Manual Quote Entry

```python
from database import SessionLocal
from repositories.author_repository import AuthorRepository
from repositories.quote_repository import QuoteRepository

db = SessionLocal()

# Get or create author
author_repo = AuthorRepository(db)
author = author_repo.get_or_create(
    name="Author Name",
    language="en"
)

# Create quote
quote_repo = QuoteRepository(db)
quote = quote_repo.create(
    text="Quote text here.",
    author_id=author.id,
    language="en"
)

db.commit()
db.close()
```

## Maintenance

### Update Search Vectors

If you need to rebuild search vectors:

```python
from database import SessionLocal
from repositories.quote_repository import QuoteRepository

db = SessionLocal()
quote_repo = QuoteRepository(db)

# Get all quotes and update vectors
from models import Quote
quotes = db.query(Quote).all()
for quote in quotes:
    quote_repo.update_search_vector(quote.id)

db.close()
```

### Database Backup

```bash
pg_dump aphorium > backup.sql
```

### Database Restore

```bash
psql aphorium < backup.sql
```

## Performance Optimization

1. **Indexes**: Ensure PostgreSQL indexes are created (run `init_database.py`)
2. **Search**: Use `prefer_bilingual=false` for faster searches if you don't need bilingual priority
3. **Pagination**: Use `limit` and `offset` parameters for large result sets
4. **Caching**: Consider adding Redis caching for popular searches (future enhancement)

## Troubleshooting

### Search Not Working

- Check that PostgreSQL full-text search indexes are created
- Verify `search_vector` column is populated
- Check database logs for errors

### Scraping Fails

- Verify network connectivity
- Check WikiQuote URLs are accessible
- Increase `SCRAPE_DELAY` in `.env` if rate-limited
- Check logs for specific errors

### Translation Matching Not Working

- Ensure authors have quotes in both languages
- Check that sources match between languages
- Verify `quote_translations` table has proper constraints

