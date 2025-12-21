# Refactoring Opportunities

This document outlines refactoring opportunities to simplify maintenance and improve code quality.

## 1. Search Service Refactoring

### Current Issues
- `SearchService.search()` method is too long (~300 lines)
- Complex bilingual pair building logic mixed with search logic
- Duplicate code for finding matching quotes
- Hard to test individual components

### Proposed Refactoring

#### Extract Bilingual Pair Builder
```python
# services/bilingual_pair_builder.py
class BilingualPairBuilder:
    """Builds bilingual quote pairs from search results."""
    
    def build_pairs(
        self,
        quotes: List[Quote],
        prefer_bilingual: bool = True
    ) -> List[Dict]:
        """Convert quotes to bilingual pairs."""
        pass
    
    def _find_matching_quote(
        self,
        quote: Quote,
        target_language: str
    ) -> Optional[Quote]:
        """Find matching quote in target language."""
        pass
```

#### Extract Query Translation Service
```python
# services/query_translation_service.py
class QueryTranslationService:
    """Handles query translation for bilingual search."""
    
    def get_search_queries(
        self,
        query: str,
        db: Session
    ) -> List[str]:
        """Get original and translated queries."""
        pass
```

#### Simplified Search Service
```python
class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.quote_repo = QuoteRepository(db)
        self.pair_builder = BilingualPairBuilder(db)
        self.query_translator = QueryTranslationService()
    
    def search(
        self,
        query: str,
        language: Optional[str] = None,
        prefer_bilingual: bool = True,
        limit: int = 50
    ) -> List[dict]:
        """Simplified search method."""
        # Get translated queries
        queries = self.query_translator.get_search_queries(query, self.db)
        
        # Search quotes
        quotes = self.quote_repo.search_multi_query(
            queries=queries,
            language=language,
            limit=limit * 2
        )
        
        # Build bilingual pairs
        return self.pair_builder.build_pairs(quotes, prefer_bilingual)
```

## 2. Repository Layer Refactoring

### Current Issues
- Search strategy pattern is good, but could be more flexible
- Translation repository has duplicate lookup logic
- Quote repository has complex duplicate detection

### Proposed Refactoring

#### Extract Duplicate Detection
```python
# repositories/duplicate_detector.py
class DuplicateDetector:
    """Detects duplicate quotes."""
    
    def is_duplicate(
        self,
        text: str,
        author_id: int,
        language: str,
        db: Session
    ) -> bool:
        """Check if quote is duplicate."""
        pass
    
    def find_similar(
        self,
        text: str,
        author_id: int,
        language: str,
        db: Session
    ) -> Optional[Quote]:
        """Find similar quote (for matching translations)."""
        pass
```

#### Simplify Quote Repository
```python
class QuoteRepository:
    def __init__(self, db: Session):
        self.db = db
        self.duplicate_detector = DuplicateDetector(db)
        self.search_strategy = get_search_strategy(db)
    
    def create(self, **kwargs) -> Quote:
        """Create quote with duplicate detection."""
        if self.duplicate_detector.is_duplicate(...):
            return self.duplicate_detector.find_similar(...)
        # Create new quote
```

## 3. Batch Loader Refactoring

### Current Issues
- Long function with nested logic
- Hard to test individual components
- Mixed concerns (scraping, database, batching)

### Proposed Refactoring

#### Extract Scraping Logic
```python
# scrapers/scraper_factory.py
class ScraperFactory:
    """Factory for creating scrapers."""
    
    @staticmethod
    def create(language: str) -> BaseScraper:
        """Create scraper for language."""
        pass
```

#### Extract Batch Processor
```python
# scrapers/batch_processor.py
class BatchProcessor:
    """Processes quotes in batches."""
    
    def __init__(self, db: Session, batch_size: int = 100):
        self.db = db
        self.batch_size = batch_size
        self.quote_repo = QuoteRepository(db)
    
    def process_batch(self, quotes: List[Dict]) -> int:
        """Process a batch of quotes."""
        pass
```

#### Simplified Batch Loader
```python
def ingest_author_batch(
    author_names: List[str],
    language: str,
    db: Session,
    batch_size: int = 100
) -> dict:
    """Simplified batch ingestion."""
    scraper = ScraperFactory.create(language)
    processor = BatchProcessor(db, batch_size)
    
    for author_name in author_names:
        data = scraper.scrape_author_page(author_name)
        processor.process_author_data(author_name, data, language)
```

## 4. Configuration Management

### Current Issues
- Settings scattered across files
- Hard to override for testing
- No validation

### Proposed Refactoring

#### Centralized Configuration
```python
# config/settings.py
class Settings(BaseSettings):
    """Application settings with validation."""
    
    database_url: str
    log_level: str = "INFO"
    batch_size: int = 100
    search_limit_max: int = 300
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

## 5. Error Handling

### Current Issues
- Inconsistent error handling
- Some functions return None, others raise exceptions
- No error recovery strategies

### Proposed Refactoring

#### Error Handling Decorator
```python
# utils/error_handling.py
def handle_db_errors(func):
    """Decorator for database error handling."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IntegrityError:
            # Handle duplicate errors
            pass
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    return wrapper
```

## 6. Testing Improvements

### Current Issues
- Test fixtures could be more reusable
- No test data factories
- Hard to test edge cases

### Proposed Refactoring

#### Test Data Factory
```python
# tests/factories.py
class QuoteFactory:
    """Factory for creating test quotes."""
    
    @staticmethod
    def create(
        db: Session,
        text: str = None,
        language: str = "en",
        author: Author = None
    ) -> Quote:
        """Create test quote."""
        pass
    
    @staticmethod
    def create_bilingual_pair(
        db: Session,
        en_text: str,
        ru_text: str,
        author: Author = None
    ) -> Tuple[Quote, Quote]:
        """Create bilingual quote pair."""
        pass
```

## 7. API Layer Refactoring

### Current Issues
- Route handlers have business logic
- No request/response validation
- Error responses inconsistent

### Proposed Refactoring

#### Extract Request Handlers
```python
# api/handlers/quote_handler.py
class QuoteHandler:
    """Handles quote-related requests."""
    
    def __init__(self, search_service: SearchService):
        self.search_service = search_service
    
    def search(
        self,
        query: str,
        language: Optional[str],
        limit: int
    ) -> List[Dict]:
        """Handle search request."""
        # Validation
        # Business logic
        # Response formatting
        pass
```

## Priority Order

1. **High Priority** (Improves maintainability significantly):
   - Extract BilingualPairBuilder from SearchService
   - Extract QueryTranslationService
   - Centralize configuration

2. **Medium Priority** (Improves testability):
   - Extract DuplicateDetector
   - Create test data factories
   - Improve error handling

3. **Low Priority** (Nice to have):
   - Refactor batch loader
   - Extract API handlers
   - Add more comprehensive logging

## Migration Strategy

1. Create new classes alongside existing code
2. Write tests for new classes
3. Gradually migrate existing code to use new classes
4. Remove old code once migration is complete
5. Update documentation

## Benefits

- **Maintainability**: Smaller, focused classes are easier to understand
- **Testability**: Individual components can be tested in isolation
- **Reusability**: Components can be reused across different parts of the codebase
- **Debugging**: Easier to identify issues in smaller functions
- **Documentation**: Clearer structure makes code self-documenting

