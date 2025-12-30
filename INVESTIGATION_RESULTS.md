# Investigation Results: source_id and Author Count Issues

## Issue 1: Why quotes don't have source_id populated

### Current Status
- **Total quotes**: 15,094
- **Quotes with source_id**: 0 (0.00%)
- **Quotes with author_id**: 14,131 (93.62%)
- **Sources in database**: 4

### Root Cause
The `scripts/attribute_quotes_to_authors.py` script **does not set source_id** when attributing quotes. 

**Problem in code** (lines 94-128):
1. The script collects all quotes from WikiQuote into a single set, losing source information:
   ```python
   all_quote_texts = set(data["quotes"])
   for quotes_list in data.get("sources", {}).values():
       all_quote_texts.update(quotes_list)
   ```

2. When matching quotes, it only sets `author_id`, not `source_id`:
   ```python
   existing_quote.author_id = author.id
   # Missing: existing_quote.source_id = source.id
   ```

3. The script doesn't create or track sources at all - it only matches quotes by text.

### Why This Happened
- Quotes were likely loaded before source tracking was fully implemented
- The `attribute_quotes_to_authors.py` script was designed to only attribute authors, not sources
- The scraper (`scrapers/ingest.py` and `scrapers/batch_loader.py`) does create sources, but those scripts weren't used to load the existing quotes

### Solution Needed
Update `scripts/attribute_quotes_to_authors.py` to:
1. Track which source each quote came from (don't merge all quotes into one set)
2. Create/get sources using `SourceRepository.get_or_create()`
3. Set `source_id` when attributing quotes, not just `author_id`

---

## Issue 2: Why only 95 authors exist

### Current Status
- **Total authors in database**: 95
- **Authors with quotes**: 85
- **Quotes without author_id**: 963 (6.38%)
- **Quotes by language**: 
  - English: 7,668
  - Russian: 7,426

### Root Cause
The `scripts/attribute_quotes_to_authors.py` script **only processes authors that already exist** in the database. It does not discover new authors.

**Problem in code** (lines 138-200):
1. The script gets all authors from the database:
   ```python
   authors = db.query(Author).all()
   ```

2. It only scrapes WikiQuote for these existing authors - it never discovers new authors

3. There are 963 orphaned quotes (no author_id) that may belong to authors not yet in the database

### Why This Happened
- The script was designed to attribute existing quotes to existing authors
- It doesn't have logic to discover new authors from orphaned quotes
- WikiQuote likely has many more authors than the 95 currently in the database

### Solution Needed
Create a new script or enhance existing one to:
1. **Discover new authors from orphaned quotes**:
   - Option A: Extract author names from quote text (if quotes contain attribution like "— Author Name")
   - Option B: Use reverse lookup - for each orphaned quote, search WikiQuote to find which author it belongs to
   - Option C: Scrape WikiQuote's author index pages to get a comprehensive list of authors

2. **Create new authors** when discovered and attribute quotes to them

3. **Process both existing and new authors** to maximize quote attribution

---

## Recommendations

### For Issue 1 (source_id):
1. Update `scripts/attribute_quotes_to_authors.py` to track and set source_id
2. Re-run the script to populate source_id for all attributed quotes
3. Consider creating a separate script to backfill source_id for quotes that already have author_id

### For Issue 2 (Author Count):
1. Create a new script `scripts/discover_authors_from_quotes.py` that:
   - Analyzes orphaned quotes to extract potential author names
   - Searches WikiQuote for matching authors
   - Creates new authors and attributes quotes
2. Or enhance `attribute_quotes_to_authors.py` to also discover new authors
3. Consider scraping WikiQuote author index pages to get a comprehensive author list

### Priority
- **Issue 1** is less critical - quotes work without source_id, it's just missing metadata
- **Issue 2** is more important - 963 quotes are orphaned and may belong to authors not in the database

