# Quote Cleanup Documentation

## Problem

The quotes table contains references, citations, and metadata mixed with actual quotes:

**Examples of bad entries:**
- `"Can Socialists Be Happy?", Tribune (20 December 1943)` - Citation
- `"The English People" (written Spring 1944, published 1947)[2]` - Reference
- `Letter to Thomas Beard (11 January 1835), in Madeline House, et al., The Letters of Charles Dickens` - Citation
- `Comment while on an American tour (March 1842), as quoted in Dickens (1949) by Hesketh Pearson` - Citation
- `The Fine Old English Gentleman (1841)` - Just a title

**Current Status:**
- Total quotes: 16,704
- Bad entries found: 3,699 (22%)
- Need cleanup: Yes

## Solution

### 1. Cleanup Script (`scripts/clean_quotes.py`)

**Features:**
- Identifies references/citations using pattern matching
- Removes citation suffixes from quotes
- Validates quotes (minimum length, sentence endings)
- Dry-run mode for safety

**Patterns Detected:**
- Publication citations: `"Title", Publication (Date)`
- References with dates: `"Title" (written Date, published Date)[number]`
- Letter citations: `Letter to ... (Date), in ...`
- Comment citations: `Comment while ... (Date), as quoted in ...`
- Publication info: `"Title" (Date), in ...`
- Short titles without sentence endings

**Usage:**
```bash
# Dry run (see what would be deleted)
python scripts/clean_quotes.py --dry-run

# Actually perform cleanup
python scripts/clean_quotes.py --execute
```

### 2. Updated Scraper (`scrapers/base.py`)

**Added `_is_valid_quote()` method:**
- Filters out references during scraping
- Prevents bad entries from being added in the future
- Validates quotes before storing

**Validation Rules:**
- Minimum length: 20 characters
- Must have sentence ending (`.`, `!`, `?`) or be >100 chars
- Must not match citation patterns
- Must not be just publication info

### 3. Linking Script (`scripts/link_existing_quotes.py`)

**Purpose:** Link existing quotes after cleanup

**What it does:**
1. Populates `bilingual_group_id` from existing translations
2. Links quotes by author + source + similarity
3. Creates `QuoteTranslation` records

**Usage:**
```bash
python scripts/link_existing_quotes.py
```

## Workflow

### Step 1: Clean Existing Quotes
```bash
# First, see what will be deleted
python scripts/clean_quotes.py --dry-run

# If looks good, execute
python scripts/clean_quotes.py --execute
```

### Step 2: Link Quotes
```bash
# Link existing quotes by author
python scripts/link_existing_quotes.py
```

### Step 3: Reload if Needed
If you want to reload quotes with the new filtering:
```bash
# Reload specific authors
python -m scrapers.batch_loader --lang en --authors-file authors.txt
```

## Results

**Before Cleanup:**
- Total quotes: 16,704
- Bad entries: 3,699 (22%)
- Clean quotes: ~13,005

**After Cleanup:**
- Bad entries removed: 3,699
- Clean quotes: ~13,005
- Quotes with citations cleaned: Variable

## Future Prevention

The updated scraper (`scrapers/base.py`) now filters out references during scraping, so future scrapes will be cleaner.

**Key Changes:**
- Added `_is_valid_quote()` validation
- Updated `extract_quotes_from_section()` to use validation
- Prevents references from being stored

## Notes

- Cleanup is **non-destructive** - you can review before executing
- Always run `--dry-run` first to see what will be deleted
- Linking script can be run multiple times safely
- Future scrapes will automatically filter references

