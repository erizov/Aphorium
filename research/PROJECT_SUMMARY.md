# Aphorium Project Summary

## Overview

Aphorium is a search engine for aphorisms and quotes from Russian and English
literature, designed to help users remember exact words and learn languages. The
system prioritizes bilingual quotes (English-Russian pairs) and is optimized
for fast text search.

## Architecture Highlights

### Layered Architecture

1. **Data Layer**: PostgreSQL with full-text search (tsvector/tsquery)
2. **Repository Layer**: Database abstraction with CRUD operations
3. **Service Layer**: Business logic for search and quote management
4. **API Layer**: FastAPI REST endpoints
5. **Scraper Layer**: WikiQuote data ingestion (RU and EN)
6. **Frontend**: Simple HTML/JS interface

### Key Design Decisions

- **PostgreSQL Full-Text Search**: Fast, native search capabilities
- **Repository Pattern**: Clean separation of database logic
- **Bilingual Priority**: System prefers quotes with translations
- **Extensible Scrapers**: Easy to add new data sources
- **No Security Layer**: MVP focus, can be added later
- **Text-Only**: No media files, optimized for text search

## Project Structure

```
Aphorium/
├── api/                    # FastAPI application
│   ├── main.py            # App entry point
│   ├── routes/            # API endpoints
│   └── models/            # Pydantic schemas
├── scrapers/              # Data ingestion
│   ├── base.py           # Base scraper class
│   ├── wikiquote_en.py   # English WikiQuote scraper
│   ├── wikiquote_ru.py   # Russian WikiQuote scraper
│   ├── matcher.py        # Translation matcher
│   └── ingest.py         # Ingestion script
├── repositories/          # Database operations
│   ├── quote_repository.py
│   ├── author_repository.py
│   ├── source_repository.py
│   └── translation_repository.py
├── services/              # Business logic
│   ├── search_service.py
│   └── quote_service.py
├── tests/                 # Test suite
│   ├── e2e/              # End-to-end tests
│   └── unit/             # Unit tests (critical modules)
├── frontend/              # Simple HTML frontend
│   └── index.html
├── alembic/              # Database migrations
├── models.py             # SQLAlchemy models
├── database.py           # Database connection
├── config.py             # Configuration
├── logger_config.py      # Logging setup
└── init_database.py      # Database initialization
```

## Database Schema

### Core Tables

- **authors**: Author information (name, language, bio)
- **sources**: Literary works (title, author, type)
- **quotes**: Individual quotes with full-text search vector
- **quote_translations**: Links between translated quotes
- **sources_metadata**: Tracking for scraped pages

### Indexes

- GIN index on `quotes.search_vector` for fast full-text search
- Indexes on `language`, `author_id` for filtering
- Unique constraints on translation pairs

## Features Implemented

### ✅ Data Ingestion

- WikiQuote EN scraper
- WikiQuote RU scraper
- Author and source extraction
- Quote extraction with normalization
- Translation matching (by author and source)

### ✅ Search Functionality

- Full-text search with PostgreSQL
- Language filtering (en, ru, both)
- Bilingual quote prioritization
- Relevance ranking
- Pagination support

### ✅ API Endpoints

- `GET /api/quotes/search` - Search quotes
- `GET /api/quotes/{id}` - Get quote with translations
- `GET /api/quotes/bilingual/pairs` - Get bilingual pairs
- `GET /api/authors` - Search authors
- `GET /api/sources` - Search sources

### ✅ Frontend

- Simple search interface
- Language filtering
- Bilingual quote highlighting
- Responsive design

### ✅ Testing

- E2E tests for ingestion workflow
- E2E tests for search functionality
- Unit tests for search service
- Unit tests for translation matcher

### ✅ Infrastructure

- Logging configuration
- Error handling
- Database initialization
- Migration support (Alembic)
- Configuration management

## Code Quality

- **PEP 8 Compliance**: All code follows PEP 8 standards
- **Type Hints**: Public functions have type annotations
- **Error Handling**: Try-except blocks with specific exceptions
- **Logging**: Structured logging throughout
- **Documentation**: Docstrings for all public functions
- **Comments**: Explanatory comments where needed

## Performance Optimizations

1. **Full-Text Search Index**: GIN index on search_vector
2. **Language Indexes**: Fast filtering by language
3. **Bilingual Prioritization**: Efficient query with JOINs
4. **Pagination**: Limit and offset for large result sets
5. **Connection Pooling**: SQLAlchemy connection management

## Future Enhancements

### Data Sources
- Project Gutenberg quotes
- Goodreads quotes
- Custom user submissions

### Features
- User favorites/bookmarks
- Quote collections
- Export functionality
- Advanced search filters
- Text similarity matching for better translation pairing

### Performance
- Redis caching for popular searches
- Elasticsearch for advanced search
- CDN for static assets

### Security (when needed)
- API authentication
- Rate limiting
- Input validation enhancements

## Testing Strategy

- **E2E Tests**: Full workflows (ingestion, search)
- **Unit Tests**: Critical modules only (search service, matcher)
- **Integration Tests**: Repository layer with test database
- **Manual Testing**: Frontend and API via browser/curl

## Usage Workflow

1. **Setup**: Install dependencies, configure database
2. **Ingest**: Scrape WikiQuote data for authors
3. **Match**: Find bilingual quote pairs
4. **Search**: Use API or frontend to search quotes
5. **Enrich**: Add more sources as needed

See [WORKFLOW.md](WORKFLOW.md) in this folder for detailed instructions.

## Dependencies

- **FastAPI**: Web framework
- **SQLAlchemy**: ORM
- **PostgreSQL**: Database (with psycopg2)
- **BeautifulSoup4**: HTML parsing
- **Requests**: HTTP client
- **Pydantic**: Data validation
- **Alembic**: Database migrations
- **Pytest**: Testing framework

## Notes

- **No AI**: As requested, no AI/ML components
- **MVP Focus**: No security layer, simple frontend
- **Text-Only**: No media support
- **Speed-Optimized**: Full-text search with proper indexing
- **Bilingual Priority**: System designed to prefer quotes with translations

## Getting Started

See [README.md](../README.md) for quick start instructions.

For detailed architecture, see [ARCHITECTURE.md](ARCHITECTURE.md) in this folder.

For workflow details, see [WORKFLOW.md](WORKFLOW.md) in this folder.

