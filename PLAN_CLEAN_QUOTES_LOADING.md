# Plan: Loading Clean Quotes (20k) Without Garbage

## Overview
Load 20,000 clean quotes (10k EN + 10k RU) with strict validation to prevent garbage entries.

## Current State
- **Cleanup script exists**: `scripts/clean_quotes.py` - removes citations, references, metadata
- **Validation exists**: `scrapers/base.py` - `_is_valid_quote()` method filters during scraping
- **Issue**: Some garbage still gets through during initial load

## Strategy: Multi-Layer Validation

### Phase 1: Pre-Load Validation (During Scraping)
**Location**: `scrapers/base.py` - `_is_valid_quote()`

**Enhancements Needed**:
1. **Stricter length requirements**:
   - Minimum: 30 characters (up from 20)
   - Must have sentence ending (`.`, `!`, `?`) OR be >150 chars
   
2. **Better citation detection**:
   - Detect publication patterns: `"Title", Publication (Date)`
   - Detect reference patterns: `"Title" (written Date, published Date)[number]`
   - Detect letter citations: `Letter to ... (Date), in ...`
   - Detect comment citations: `Comment while ... (Date), as quoted in ...`
   
3. **Title detection**:
   - Reject Title Case without sentence endings
   - Reject patterns like: `"Title: Subtitle"`
   - Reject standalone book titles
   
4. **Quote indicators**:
   - Prefer quotes with quotation marks (but not required)
   - Prefer quotes with attribution patterns
   - Reject pure metadata

### Phase 2: Batch Loading with Validation
**Location**: `scrapers/batch_loader.py` - `ingest_author_batch()`

**Enhancements Needed**:
1. **Additional validation before insert**:
   ```python
   # Before adding to batch
   if not _is_valid_quote_strict(quote_text):
       continue
   ```

2. **Batch validation**:
   - Validate entire batch before commit
   - Skip batches with >50% invalid quotes
   - Log validation failures

### Phase 3: Post-Load Cleanup
**Location**: `scripts/clean_quotes.py`

**Current**: Already exists and works well
**Usage**: Run after loading completes

## Implementation Steps

### Step 1: Enhance `_is_valid_quote()` in `scrapers/base.py`

```python
def _is_valid_quote(self, text: str) -> bool:
    """
    Strict validation for quotes.
    
    Returns False for:
    - Citations and references
    - Publication metadata
    - Book titles without quotes
    - Too short entries
    - Entries without sentence structure
    """
    # Existing checks...
    
    # NEW: Stricter length (30 chars minimum)
    if len(text) < 30:
        return False
    
    # NEW: Must have sentence ending OR be very long
    has_ending = any(text.rstrip().endswith(p) for p in ['.', '!', '?', '…'])
    if not has_ending and len(text) < 150:
        return False
    
    # NEW: Reject Title Case without sentence endings
    if text.istitle() and not has_ending:
        return False
    
    # NEW: Reject common citation patterns
    citation_patterns = [
        r'^"[^"]+",\s+[A-Z][^,]+(?:,\s*\d{1,2}\s+\w+\s+\d{4})',
        r'^"[^"]+"\s*\([^)]*(?:written|published)[^)]*\)\s*\[\d+\]$',
        r'^Letter\s+to\s+[^,]+,\s*\([^)]+\),\s*(?:in|as|as quoted in)',
        r'^Comment\s+while\s+[^,]+,\s*\([^)]+\),\s*as quoted in',
    ]
    for pattern in citation_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return False
    
    return True
```

### Step 2: Add Batch Validation in `scrapers/batch_loader.py`

```python
def _validate_quote_batch(quotes: List[str]) -> List[str]:
    """Validate batch of quotes, return only valid ones."""
    from scrapers.base import BaseScraper
    
    # Create temporary scraper instance for validation
    scraper = BaseScraper()
    valid_quotes = []
    
    for quote in quotes:
        if scraper._is_valid_quote(quote):
            valid_quotes.append(quote)
        else:
            logger.debug(f"Rejected quote: {quote[:50]}...")
    
    return valid_quotes
```

### Step 3: Update Batch Loader to Use Validation

```python
# In ingest_author_batch()
for quote_text in quotes:
    # Validate before adding to batch
    if not scraper._is_valid_quote(quote_text):
        logger.debug(f"Skipping invalid quote: {quote_text[:50]}...")
        continue
    
    quotes_batch.append({...})
```

### Step 4: Create Resumable Quote Loader Script

**New file**: `scripts/load_clean_quotes_batch.py`

**Features**:
- Loads quotes in batches of 1000
- Validates each quote before insertion
- Tracks progress (which authors processed)
- Resumable (can stop and resume)
- Target: 20k clean quotes (10k EN + 10k RU)
- Runs cleanup after each batch

**Usage**:
```bash
# Load clean quotes
python scripts/load_clean_quotes_batch.py --target-quotes 20000

# Resume from last position
python scripts/load_clean_quotes_batch.py
```

## Validation Rules Summary

### ✅ ACCEPT Quotes That:
- Are 30+ characters long
- Have sentence endings (`.`, `!`, `?`) OR are 150+ chars
- Contain actual quoted speech/content
- Are not citations or references
- Are not book titles

### ❌ REJECT Quotes That:
- Are < 30 characters
- Are citations: `"Title", Publication (Date)`
- Are references: `"Title" (written Date)[2]`
- Are letter citations: `Letter to ... (Date), in ...`
- Are book titles without quotes
- Are Title Case without sentence endings
- Are pure metadata

## Expected Results

- **20,000 clean quotes** (10k EN + 10k RU)
- **< 1% garbage** (vs current ~22%)
- **Resumable loading** (can stop/resume)
- **CSV backup** of all loaded quotes

## Testing Plan

1. **Test validation**:
   ```bash
   python -c "from scrapers.base import BaseScraper; s = BaseScraper(); print(s._is_valid_quote('Test quote.'))"
   ```

2. **Dry run**:
   ```bash
   python scripts/load_clean_quotes_batch.py --dry-run --target-quotes 1000
   ```

3. **Small batch test**:
   ```bash
   python scripts/load_clean_quotes_batch.py --target-quotes 1000 --max-authors 5
   ```

4. **Full load**:
   ```bash
   python scripts/load_clean_quotes_batch.py --target-quotes 20000
   ```

## Files to Modify

1. `scrapers/base.py` - Enhance `_is_valid_quote()`
2. `scrapers/batch_loader.py` - Add batch validation
3. `scripts/load_clean_quotes_batch.py` - NEW: Resumable clean quote loader

## Files to Create

1. `scripts/load_clean_quotes_batch.py` - Main loader script
2. `data/quote_loading_progress.json` - Progress tracking

