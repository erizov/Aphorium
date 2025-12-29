# Testing Guide for Database Schema Improvements and Refactoring

## Overview

This guide explains how to test the new database schema improvements and refactored code.

## Changes Made

### 1. Database Schema
- Added `bilingual_group_id` column to `quotes` table
- Added indexes for fast bilingual pair retrieval
- Migration helper in `init_database.py`

### 2. New Services
- `BilingualLinker`: Links EN and RU quotes
- `BilingualPairBuilder`: Builds bilingual pairs (extracted from SearchService)
- `QueryTranslationService`: Handles query translation (extracted from search logic)

### 3. Refactored Code
- `SearchService` simplified (new version in `search_service_refactored.py`)
- Repository updates for `bilingual_group_id` support

## Testing Steps

### Step 1: Update Database Schema

```bash
# This will add bilingual_group_id column if it doesn't exist
python init_database.py
```

**Expected output:**
- "Adding bilingual_group_id column to quotes table..." (if column doesn't exist)
- "✅ Added bilingual_group_id column and indexes"
- "Database initialization complete"

### Step 2: Populate Bilingual Groups

```bash
# This will scan existing translations and assign group IDs
python scripts/populate_bilingual_groups.py
```

**Expected output:**
- "Populating bilingual_group_id from existing translations..."
- "✅ Created X bilingual groups"
- "Linking remaining quotes by author..."
- "✅ Created Y additional links"

### Step 3: Test Search Functionality

**Option A: Use existing SearchService (backward compatible)**
- Current API should work as before
- Test search queries: "love", "God", "любовь"

**Option B: Test refactored SearchService**
- Update `api/routes/quotes.py` to import from `search_service_refactored`
- Test same queries

### Step 4: Verify Bilingual Pairs

```python
# Test script
from database import SessionLocal
from services.bilingual_pair_builder import BilingualPairBuilder
from repositories.quote_repository import QuoteRepository

db = SessionLocal()
pair_builder = BilingualPairBuilder(db)
quote_repo = QuoteRepository(db)

# Get quotes with bilingual_group_id
quotes = quote_repo.search("love", limit=10)

# Build pairs
pairs = pair_builder.build_pairs(quotes)

# Verify pairs have both EN and RU
for pair in pairs:
    print(f"EN: {pair.get('english')}")
    print(f"RU: {pair.get('russian')}")
    print("---")
```

### Step 5: Test Linking Service

```python
# Test script
from database import SessionLocal
from services.bilingual_linker import BilingualLinker

db = SessionLocal()
linker = BilingualLinker(db)

# Link quotes for a specific author
# (Replace with actual author ID from your database)
author_id = 1
links_created = linker.find_matches_by_author(author_id)
print(f"Created {links_created} links")
```

### Step 6: Performance Test

Compare query times before/after:

```python
import time
from database import SessionLocal
from services.search_service import SearchService
from services.search_service_refactored import SearchService as RefactoredSearchService

db = SessionLocal()

# Old service
old_service = SearchService(db)
start = time.time()
results_old = old_service.search("love", limit=50)
time_old = time.time() - start

# New service
new_service = RefactoredSearchService(db)
start = time.time()
results_new = new_service.search("love", limit=50)
time_new = time.time() - start

print(f"Old service: {time_old:.3f}s, {len(results_old)} results")
print(f"New service: {time_new:.3f}s, {len(results_new)} results")
```

## Verification Checklist

- [ ] Database schema updated (bilingual_group_id column exists)
- [ ] Indexes created (check with `\d quotes` in PostgreSQL)
- [ ] Existing translations have group IDs assigned
- [ ] Search returns bilingual pairs correctly
- [ ] Performance improved (faster queries)
- [ ] No errors in logs
- [ ] API endpoints work as before

## Rollback Plan

If something goes wrong:

1. **Database rollback:**
   ```sql
   ALTER TABLE quotes DROP COLUMN bilingual_group_id;
   DROP INDEX IF EXISTS idx_quotes_bilingual_group;
   DROP INDEX IF EXISTS idx_quotes_group_language;
   ```

2. **Code rollback:**
   - Keep using old `SearchService` (it's still there)
   - Don't use refactored services yet

## Next Steps After Testing

1. If everything works:
   - Switch API to use refactored SearchService
   - Remove old SearchService (or keep for reference)
   - Implement web scraping for linking

2. If issues found:
   - Report issues
   - Fix bugs
   - Re-test

## Notes

- Old `SearchService` is still available for backward compatibility
- New services are in separate files for easy testing
- Migration is non-destructive (doesn't delete existing data)
- Can run migration multiple times safely

