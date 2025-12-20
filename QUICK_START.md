# Quick Start Guide

## 1. Setup (One Time)

```bash
# Install dependencies
pip install -r requirements.txt

# Configure database

# Option A: Use SQLite (Easiest - no PostgreSQL needed)
python setup_database_sqlite.py

# Option B: Use PostgreSQL (Better for production)
# First install PostgreSQL (see [research/POSTGRESQL_SETUP.md](research/POSTGRESQL_SETUP.md))
# Then:
python setup_database.py
# Or manually:
python init_database.py
```

## 2. Load Data

### Recommended: Load Bilingual Authors

```bash
# Load English quotes from bilingual authors
python -m scrapers.batch_loader --lang en --mode bilingual --workers 3

# Load Russian quotes from bilingual authors
python -m scrapers.batch_loader --lang ru --mode bilingual --workers 3

# Match translations
python match_translations.py
```

This will load ~20-30 popular authors that exist in both languages,
resulting in ~5,000-10,000 quotes with bilingual pairs.

### Alternative: Load Specific Authors

```bash
# Single author
python -m scrapers.ingest --lang en --author "William Shakespeare"
python -m scrapers.ingest --lang ru --author "Александр Пушкин"

# From file
python -m scrapers.batch_loader --lang en --authors-file authors.txt
```

## 3. Start Application

**Windows:**
```powershell
.\start_app.ps1
```

**Linux/Mac:**
```bash
./start_app.sh
```

This starts both:
- **Backend API** at http://localhost:8000
- **Frontend** at http://localhost:3000

## 4. Stop Application

**Windows:**
```powershell
.\stop_app.ps1
```

**Linux/Mac:**
```bash
./stop_app.sh
```

## 5. Use Frontend

Open http://localhost:3000 in your browser.

**Features:**
- Search works in both English and Russian
- Type "love" or "любовь" - both will find relevant quotes
- Results show quotes in both languages
- Bilingual quotes are highlighted

## 6. Search Examples

Try these searches:
- `love` - finds quotes about love in both languages
- `любовь` - finds quotes about love in Russian
- `wisdom` - finds quotes about wisdom
- `мудрость` - finds quotes about wisdom in Russian
- `Shakespeare` - finds quotes by Shakespeare
- `Пушкин` - finds quotes by Pushkin

## Tips

1. **Start Small**: Load 5-10 authors first to test
2. **Bilingual Priority**: The system prefers quotes with translations
3. **Search is Smart**: Searches both languages automatically
4. **Batch Loading**: Use batch loader for faster ingestion
5. **Parallel Workers**: Adjust `--workers` based on your network (2-3 recommended)

## Troubleshooting

**Server won't start:**
- Check if port 8000 is available
- Verify database connection in `.env`
- Run `python init_database.py` again

**No search results:**
- Make sure data has been loaded
- Check API is running: http://localhost:8000/health
- Verify database has quotes: Check with `psql` or database tool

**Scraping fails:**
- Check internet connection
- Increase `SCRAPE_DELAY` in `.env` (rate limiting)
- Try fewer workers: `--workers 2`

