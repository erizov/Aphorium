# Aphorium Architecture

## Overview

Aphorium is a search engine for aphorisms and quotes from Russian and English
literature, designed to help users remember exact words and learn languages.
The system prioritizes bilingual quotes (English-Russian pairs) and is optimized
for fast text search.

## Architecture Principles

1. **Text-only**: No media files (images, audio, video)
2. **Speed-optimized**: PostgreSQL full-text search with proper indexing
3. **Bilingual priority**: Prefer quotes with both English and Russian versions
4. **Extensible**: Designed for future enrichment from multiple sources
5. **MVP focus**: No security layer for initial version
6. **Best practices**: PEP 8, type hints, logging, error handling

## System Components

### 1. Data Layer

**Database**: PostgreSQL
- Full-text search capabilities (tsvector/tsquery)
- ACID compliance for data integrity
- Efficient indexing for search performance

**Schema**:
- `authors`: Author information (name, language, bio)
- `sources`: Literary works (title, author, type)
- `quotes`: Individual quotes (text, author, source, language)
- `quote_translations`: Links between translated quotes
- `sources_metadata`: WikiQuote page metadata for tracking

### 2. Data Ingestion Layer

**WikiQuote Scrapers**:
- `scrapers/wikiquote_ru.py`: Russian WikiQuote scraper
- `scrapers/wikiquote_en.py`: English WikiQuote scraper
- `scrapers/base.py`: Base scraper with common functionality
- `scrapers/matcher.py`: Matches English/Russian quote pairs

**Process**:
1. Fetch WikiQuote pages (author pages, work pages)
2. Extract quotes with metadata
3. Normalize and clean text
4. Store in database
5. Match bilingual pairs based on author/source similarity

### 3. Repository Layer

**Pattern**: Repository pattern for database abstraction
- `repositories/quote_repository.py`: Quote CRUD operations
- `repositories/author_repository.py`: Author operations
- `repositories/source_repository.py`: Source operations
- `repositories/translation_repository.py`: Translation matching

### 4. Service Layer

**Search Service**:
- `services/search_service.py`: Full-text search logic
- PostgreSQL tsvector indexes for fast search
- Ranking by relevance and bilingual preference
- Language filtering

**Quote Service**:
- `services/quote_service.py`: Business logic for quotes
- Bilingual pair retrieval
- Quote enrichment and validation

### 5. API Layer

**FastAPI Application**:
- `api/main.py`: Application entry point
- `api/routes/quotes.py`: Quote search endpoints
- `api/routes/authors.py`: Author endpoints
- `api/routes/sources.py`: Source endpoints
- `api/models/schemas.py`: Pydantic models for request/response

**Endpoints**:
- `GET /api/quotes/search?q=text&lang=en|ru|both`
- `GET /api/quotes/{id}`
- `GET /api/quotes/{id}/translations`
- `GET /api/authors?name=...`
- `GET /api/sources?title=...`

### 6. Frontend

**Simple HTML/JS** (MVP):
- `frontend/index.html`: Search interface
- Basic search form
- Results display with bilingual pairs highlighted
- No framework for MVP (can upgrade to React later)

## Data Flow

### Ingestion Flow
```
WikiQuote Pages → Scrapers → Data Normalization → Repository → Database
                                                              ↓
                                                    Translation Matcher
```

### Search Flow
```
User Query → API → Search Service → Repository → PostgreSQL Full-Text Search
                                                      ↓
                                            Results Ranking → API Response
```

## Database Schema

```sql
CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    language VARCHAR(10) NOT NULL,  -- 'en' or 'ru'
    bio TEXT,
    wikiquote_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    author_id INTEGER REFERENCES authors(id),
    source_type VARCHAR(50),  -- 'book', 'play', 'poem', etc.
    language VARCHAR(10) NOT NULL,
    wikiquote_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE quotes (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    author_id INTEGER REFERENCES authors(id),
    source_id INTEGER REFERENCES sources(id),
    language VARCHAR(10) NOT NULL,
    search_vector tsvector,  -- For full-text search
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_quotes_search ON quotes USING GIN(search_vector);
CREATE INDEX idx_quotes_language ON quotes(language);
CREATE INDEX idx_quotes_author ON quotes(author_id);

CREATE TABLE quote_translations (
    id SERIAL PRIMARY KEY,
    quote_id INTEGER REFERENCES quotes(id),
    translated_quote_id INTEGER REFERENCES quotes(id),
    confidence INTEGER DEFAULT 0,  -- 0-100, manual or auto-matched
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(quote_id, translated_quote_id)
);

CREATE TABLE sources_metadata (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,  -- 'wikiquote_ru', 'wikiquote_en'
    page_url VARCHAR(500) NOT NULL,
    last_scraped TIMESTAMP,
    status VARCHAR(50),  -- 'pending', 'completed', 'failed'
    UNIQUE(source_type, page_url)
);
```

## Search Optimization

1. **Full-Text Search Index**: GIN index on `search_vector` column
2. **Language Filtering**: Index on `language` column
3. **Bilingual Priority**: JOIN with `quote_translations` to boost bilingual
   results
4. **Query Optimization**: Use prepared statements, limit result sets

## Future Enhancements

1. **Additional Sources**: 
   - Project Gutenberg quotes
   - Goodreads quotes
   - Custom user submissions

2. **Features**:
   - User favorites/bookmarks
   - Quote collections
   - Export functionality
   - API rate limiting
   - Authentication (if needed)

3. **Performance**:
   - Redis caching for popular searches
   - Elasticsearch for advanced search
   - CDN for static assets

## Testing Strategy

1. **E2E Tests**: 
   - Full ingestion workflow
   - Search functionality
   - Bilingual matching

2. **Unit Tests** (critical modules only):
   - Search service logic
   - Translation matcher
   - Text normalization

3. **Integration Tests**:
   - Repository layer with test database
   - API endpoints

## Logging

- Structured logging with Python `logging` module
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Log scraping progress, search queries, errors
- File and console output

## Error Handling

- Try-except blocks with specific exception types
- Graceful degradation (continue on single quote failure)
- Retry logic for network requests
- Database transaction rollback on errors

