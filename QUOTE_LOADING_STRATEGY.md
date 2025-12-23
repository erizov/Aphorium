# Quote Loading Strategy: English and Russian Quotes (No Translation Service)

## Overview

This document describes how to load English and Russian quotes directly into the `quotes` table without using a translation service. The strategy uses multi-layer validation to ensure only clean, valid quotes are loaded, rejecting garbage like names, numbers, references, citations, and metadata.

## Loading Process

### 1. **Scraping Phase**
- Use `WikiQuoteEnScraper` for English quotes
- Use `WikiQuoteRuScraper` for Russian quotes
- Scrape quotes from WikiQuote pages for each author
- Extract quotes from HTML sections, skipping navigation/reference sections

### 2. **Pre-Load Validation** (First Filter)
- Each quote is validated using `scraper._is_valid_quote()` before being added to batch
- Invalid quotes are rejected immediately (not added to batch)

### 3. **Batch Validation** (Second Filter)
- Before inserting a batch, validate all quotes again
- If >50% of batch is invalid, skip entire batch (likely corrupted data)
- Log rejection rate for monitoring

### 4. **Post-Load Cleanup** (Third Filter)
- After loading, run `clean_quotes()` script
- Removes any references/citations that passed initial validation
- Final cleanup pass to ensure database quality

### 5. **Database Insert**
- Insert validated quotes with:
  - `text`: Quote text (normalized)
  - `author_id`: Author reference
  - `source_id`: Source reference (if available)
  - `language`: 'en' or 'ru'

## Complete Rejection Filters

### **Length Filters**
```python
# REJECT if:
- Text is empty or None
- Length < 30 characters (too short to be a meaningful quote)
- After removing quotes, length < 30 characters
```

### **Sentence Structure Filters**
```python
# REJECT if:
- No sentence ending (. ! ? …) AND length < 150 characters
  (Long quotes without endings are acceptable, short ones are not)
- Title Case without sentence endings (likely book titles)
  Example: "The Great Gatsby" (no period) → REJECT
```

### **Citation and Reference Patterns**

#### Publication Citations
```python
# REJECT patterns like:
- "Title", Publication (Date)
- "Title" (written Date, published Date)[number]
- "Title" (Date), in ...
- Letter to ... (Date), in ...
- Comment while ... (Date), as quoted in ...
```

#### Chapter/Part/Section References
```python
# REJECT if contains:
- Ch. X, Ch X, Chapter X (anywhere in text)
- Гл. X, Глава X (Russian chapter references)
- Part I, Part 1, Part One, Part A (English)
- Часть I, Часть 1, Часть первая (Russian)
- Section 1, Section A (English)
- Раздел 1, Секция 1 (Russian)
- Article 1, Article I (English)
- Статья 1 (Russian)
- Act III, scene ii, Act 1, Scene 2
- Scenes, Ch. X
- Volume references: Vol. 3, Volume 2, Том 3
```

#### Play/Theater References
```python
# REJECT if contains:
- Act III, scene ii
- Act 1, Scene 2
- Act [IVX]+ (anywhere)
- Scene [number] (anywhere)
- Scenes, (at start)
- Сцена [number] (Russian)
```

### **Metadata and Navigation**

#### Reference Markers
```python
# REJECT if:
- Starts with ↑ (upward arrow - footnote reference)
- Contains "см." or "См." anywhere (Russian "see" - reference marker)
- Starts with "Категория:" or "категория:" (Russian "Category:")
- Contains "Famous Quotations" or "Quotations"
```

#### URLs and Links
```python
# REJECT if contains:
- http:// or https://
- www.
```

### **Publication Information**

#### Publishing Houses
```python
# REJECT if contains:
- Published by [Name]
- Publisher: [Name]
- Publishing house names:
  * Penguin, Random House, HarperCollins
  * Simon & Schuster, Macmillan, Hachette
  * Oxford University Press, Cambridge University Press
  * Harvard University Press, MIT Press
  * Princeton University Press, Yale University Press
  * University Press, Press, Publishers, Publishing
  * Editions, Books
- Издательство: [Name] (Russian)
- Издатель: [Name] (Russian)
```

#### Publication Patterns
```python
# REJECT if contains:
- published as
- published by
- Published as
- Published by
```

### **Author and Title Patterns**

#### Author Citations
```python
# REJECT if contains:
- by [Author Name] (English)
- автор: [Author Name] (Russian)
- Pattern: by [Capital] [lowercase]+ (multiple words)
```

#### Book Title Patterns
```python
# REJECT if matches:
- Title (Year) - no sentence ending
  Example: "The Great Gatsby (1925)" → REJECT
- Title, Subtitle - no sentence ending
  Example: "War and Peace, Part One" → REJECT
- Title: Subtitle - no sentence ending
  Example: "1984: A Novel" → REJECT
```

### **Date Patterns**
```python
# REJECT if contains:
- (20 December 1943) - English date format
- (20 декабря 1943) - Russian date format
- (1943) - Year only in parentheses
- Combined with publication info
```

### **Reference Numbers**
```python
# REJECT if contains:
- [1], [2], [3] - Reference numbers in brackets
```

### **Place Names and Locations**
```python
# REJECT if contains:
- Publishing locations in citation format
- Place names in parentheses with dates
```

## Positive Indicators (Keep These)

A quote is more likely to be valid if it has:

```python
# KEEP if has:
- Sentence ending (. ! ? …)
- Quote verbs: said, wrote, quoted, remarked, declared, stated
- Long quoted text: "..." (20+ characters)
- Proper sentence structure
- Meaningful content (not just metadata)
```

## Validation Flow

```
Raw Quote Text
    ↓
1. Normalize (remove extra whitespace, surrounding quotes)
    ↓
2. Length Check (< 30 chars → REJECT)
    ↓
3. Sentence Ending Check (no ending AND < 150 chars → REJECT)
    ↓
4. Title Case Check (Title Case + no ending → REJECT)
    ↓
5. Citation Pattern Check (matches citation → REJECT)
    ↓
6. Reference Pattern Check (matches reference → REJECT)
    ↓
7. Metadata Check (contains metadata → REJECT)
    ↓
8. Publication Info Check (contains pub info → REJECT)
    ↓
9. URL Check (contains URL → REJECT)
    ↓
10. Chapter/Part/Section Check (contains ref → REJECT)
    ↓
11. Author/Title Pattern Check (matches pattern → REJECT)
    ↓
VALID QUOTE → Add to batch
```

## Batch Processing

### Batch Size
- Default: 100 quotes per batch
- Configurable via `--batch-size` parameter

### Batch Validation
- Before insert: validate all quotes in batch
- If >50% invalid: skip entire batch (log warning)
- If <50% invalid: insert only valid quotes

### Commit Strategy
- Commit after each batch
- Rollback on error
- Log batch statistics

## Post-Load Cleanup

After loading quotes, run cleanup script:

```python
from scripts.clean_quotes import clean_quotes

# Clean all quotes in database
clean_quotes()
```

This removes any references/citations that passed initial validation.

## Example: Valid vs Invalid Quotes

### ✅ VALID QUOTES (Will be loaded)

```
English:
"The only way to do great work is to love what you do."
"To be or not to be, that is the question."
"In the middle of difficulty lies opportunity."

Russian:
"Единственный способ делать великую работу — это любить то, что ты делаешь."
"Быть или не быть — вот в чём вопрос."
"В середине трудности лежит возможность."
```

### ❌ INVALID QUOTES (Will be rejected)

```
Citations:
"Can Socialists Be Happy?", Tribune (20 December 1943)
"The English People" (written Spring 1944, published 1947)[2]

References:
Letter to Thomas Beard (11 January 1835), in...
Comment while visiting..., (Date), as quoted in...

Chapter References:
"Title" (Date), Ch. 22
"Title", Chapter 5
Гл. 3, Глава 10

Part/Section References:
Part I, Part 1, Часть I
Section 1, Раздел 1
Act III, scene ii

Metadata:
↑ (footnote reference)
см. (Russian reference marker)
Категория: Философия

Publishing Info:
Published by Penguin Books
Издательство: АСТ

URLs:
https://example.com
www.example.com

Titles without quotes:
The Great Gatsby (1925)
War and Peace, Part One
```

## Implementation Code

### Main Loading Function

```python
def load_quotes_without_translation(
    author_names: List[str],
    language: str,  # 'en' or 'ru'
    batch_size: int = 100
) -> dict:
    """
    Load quotes directly into database without translation.
    
    Uses multi-layer validation to ensure only clean quotes are loaded.
    """
    stats = {
        "authors_processed": 0,
        "quotes_created": 0,
        "quotes_rejected": 0
    }
    
    # Initialize scraper
    if language == "en":
        scraper = WikiQuoteEnScraper()
    elif language == "ru":
        scraper = WikiQuoteRuScraper()
    else:
        raise ValueError(f"Unsupported language: {language}")
    
    db = SessionLocal()
    quote_repo = QuoteRepository(db)
    author_repo = AuthorRepository(db)
    
    quotes_batch = []
    
    for author_name in author_names:
        # Get or create author
        author = author_repo.get_or_create(name=author_name, language=language)
        
        # Scrape quotes
        data = scraper.scrape_author(author_name)
        
        # Process quotes with validation
        for quote_text in data.get("quotes", []):
            # PRE-LOAD VALIDATION (First filter)
            if not scraper._is_valid_quote(quote_text):
                stats["quotes_rejected"] += 1
                continue
            
            quotes_batch.append({
                "text": quote_text,
                "author_id": author.id,
                "source_id": None,
                "language": language
            })
            
            # BATCH VALIDATION (Second filter)
            if len(quotes_batch) >= batch_size:
                validated_batch = _validate_batch(quotes_batch, scraper)
                
                # Insert validated batch
                for quote_data in validated_batch:
                    quote_repo.create(**quote_data)
                db.commit()
                
                stats["quotes_created"] += len(validated_batch)
                quotes_batch = []
        
        stats["authors_processed"] += 1
    
    # Insert remaining quotes
    if quotes_batch:
        validated_batch = _validate_batch(quotes_batch, scraper)
        for quote_data in validated_batch:
            quote_repo.create(**quote_data)
        db.commit()
        stats["quotes_created"] += len(validated_batch)
    
    db.close()
    
    # POST-LOAD CLEANUP (Third filter)
    if CLEANUP_AVAILABLE:
        clean_quotes()
    
    return stats
```

## Summary

The quote loading strategy uses **three layers of validation**:

1. **Pre-Load**: Validate each quote before adding to batch
2. **Batch Validation**: Validate entire batch before insert
3. **Post-Load Cleanup**: Final cleanup pass

This ensures only clean, valid quotes are loaded, rejecting:
- Citations and references
- Chapter/part/section references
- Publication metadata
- URLs and links
- Book titles without quotes
- Author citations
- Date patterns in citations
- Reference markers
- Navigation elements

The result is a clean database with only meaningful quotes, no garbage.

