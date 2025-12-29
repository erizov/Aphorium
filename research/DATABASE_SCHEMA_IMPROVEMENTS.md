# Database Schema Improvements for Bilingual Quotes

## Current Structure Analysis

**Current Approach:**
- Separate `Quote` records for EN and RU
- `QuoteTranslation` table links quotes bidirectionally
- Requires JOINs to get bilingual pairs

**Issues:**
- Slow retrieval of bilingual pairs (requires JOINs)
- No direct grouping mechanism
- Translation lookup is bidirectional but not optimized

## Proposed Solutions

### Option 1: Add `bilingual_group_id` to Quotes Table (RECOMMENDED)

**Pros:**
- Fast retrieval (direct grouping, no JOINs needed)
- Maintains current structure (separate records)
- Allows multiple translations per quote
- Easy to query: `WHERE bilingual_group_id = X`
- Can still use QuoteTranslation for metadata

**Cons:**
- Requires migration
- Need to populate group IDs for existing quotes

**Implementation:**
```sql
ALTER TABLE quotes ADD COLUMN bilingual_group_id INTEGER;
CREATE INDEX idx_quotes_bilingual_group ON quotes(bilingual_group_id);
```

**Usage:**
- When linking quotes, assign same `bilingual_group_id`
- Query: `SELECT * FROM quotes WHERE bilingual_group_id = ? ORDER BY language`
- Returns both EN and RU quotes in one query

### Option 2: Add `text_en` and `text_ru` Columns

**Pros:**
- Single row per quote pair
- Very fast retrieval

**Cons:**
- Loses flexibility (can't have multiple translations)
- Data duplication
- Breaks current structure significantly
- Harder to maintain

### Option 3: Materialized View

**Pros:**
- Fast read access
- Doesn't change base tables

**Cons:**
- Needs refresh
- Database-specific (PostgreSQL)
- More complex

## Recommendation: Option 1 with Improvements

1. Add `bilingual_group_id` to quotes table
2. Improve `QuoteTranslation` table with better indexes
3. Create helper methods for fast bilingual pair retrieval
4. Add migration script

## Linking Mechanism

### Strategy 1: Author + Source Matching (Current)
- Match quotes from same author and source
- Use text similarity (4+ words match)

### Strategy 2: Web Scraping for Official Translations
- Scrape bilingual quote websites
- Match by author + known quote text
- Store as high-confidence translations

### Strategy 3: Translation API (Fallback)
- Use translation APIs for unmatched quotes
- Lower confidence score
- Can be improved manually later

### Strategy 4: Bidirectional Auto-Linking
- When EN->RU translation is created, auto-create RU->EN link
- Ensure symmetry in QuoteTranslation table

## Implementation Plan

1. **Database Migration:**
   - Add `bilingual_group_id` column
   - Add indexes
   - Create migration script

2. **Linking Service:**
   - Create `BilingualLinker` service
   - Implement multiple matching strategies
   - Auto-link bidirectional translations

3. **Repository Updates:**
   - Add methods to get quotes by `bilingual_group_id`
   - Optimize bilingual pair retrieval

4. **Refactoring:**
   - Extract BilingualPairBuilder
   - Extract QueryTranslationService
   - Simplify SearchService

