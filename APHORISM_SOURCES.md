# Additional Sources for Aphorisms (English and Russian)

This document lists alternative sources for loading aphorisms and quotes beyond WikiQuote.

## English Sources

### 1. **Goodreads Quotes**
- **URL**: https://www.goodreads.com/quotes
- **Pros**: Large collection, well-organized by author/book, user ratings
- **Cons**: Requires scraping, may have rate limits
- **Format**: HTML with quote text, author, book title
- **Implementation**: Scrape quote pages, extract text and metadata

### 2. **BrainyQuote**
- **URL**: https://www.brainyquote.com
- **Pros**: Very large database, categorized by topic/author
- **Cons**: May have ads, requires careful scraping
- **Format**: HTML with quote text and author
- **Implementation**: Scrape author pages or topic pages

### 3. **AZQuotes**
- **URL**: https://www.azquotes.com
- **Pros**: Large collection, good author organization
- **Cons**: Requires scraping
- **Format**: HTML with quote text, author, source
- **Implementation**: Similar to WikiQuote scraping

### 4. **The Quotations Page**
- **URL**: http://www.quotationspage.com
- **Pros**: Classic source, well-organized
- **Cons**: Older site, may have limited modern quotes
- **Format**: HTML with quote text and author
- **Implementation**: Scrape author or topic pages

### 5. **Project Gutenberg**
- **URL**: https://www.gutenberg.org
- **Pros**: Free public domain books, can extract quotes from full texts
- **Cons**: Requires text processing to extract meaningful quotes
- **Format**: Plain text files (books)
- **Implementation**: 
  - Download books by famous authors
  - Extract sentences that look like quotes (quotation marks, attribution patterns)
  - Filter using existing validation logic

### 6. **Poetry Foundation**
- **URL**: https://www.poetryfoundation.org
- **Pros**: High-quality poetry quotes, well-curated
- **Cons**: Focused on poetry, may need filtering
- **Format**: HTML with poem excerpts
- **Implementation**: Scrape poem pages, extract notable lines

### 7. **Bartleby.com**
- **URL**: https://www.bartleby.com
- **Pros**: Classic literature collection, public domain
- **Cons**: Older interface, may need text processing
- **Format**: HTML with full texts
- **Implementation**: Extract quotes from literature texts

### 8. **Quote Investigator**
- **URL**: https://quoteinvestigator.com
- **Pros**: Verified quotes with sources, high quality
- **Cons**: Smaller collection, focused on verification
- **Format**: HTML articles with verified quotes
- **Implementation**: Scrape article pages for verified quotes

### 9. **Reddit Quotes Subreddits**
- **URL**: https://www.reddit.com/r/quotes, https://www.reddit.com/r/QuotesPorn
- **Pros**: Community-curated, diverse sources
- **Cons**: Variable quality, requires filtering
- **Format**: Reddit API or scraping
- **Implementation**: Use Reddit API to fetch top posts, extract quotes

### 10. **Wikiquote (Alternative Languages)**
- **URL**: https://en.wikiquote.org (already using)
- **Pros**: Already integrated, can expand to other language versions
- **Cons**: Already using English/Russian
- **Format**: Same as current implementation
- **Implementation**: Already implemented

## Russian Sources

### 1. **Афоризмы.ру**
- **URL**: https://aphorisms.ru
- **Pros**: Large Russian aphorism collection, well-organized
- **Cons**: Requires scraping, may have ads
- **Format**: HTML with quote text and author
- **Implementation**: Scrape author pages or category pages

### 2. **Цитаты.ру**
- **URL**: https://citaty.ru
- **Pros**: Good collection of Russian quotes
- **Cons**: Requires scraping
- **Format**: HTML with quote text, author, source
- **Implementation**: Similar to WikiQuote scraping

### 3. **Lib.ru (Russian Digital Library)**
- **URL**: http://lib.ru
- **Pros**: Large collection of Russian literature, public domain
- **Cons**: Requires text processing to extract quotes
- **Format**: Plain text files (books)
- **Implementation**: 
  - Download Russian literature texts
  - Extract quotes using quotation marks and attribution patterns
  - Filter using validation logic

### 4. **Русская Поэзия (Russian Poetry)**
- **URL**: Various sites like http://www.russianpoetry.ru
- **Pros**: High-quality poetry quotes
- **Cons**: Focused on poetry, may need filtering
- **Format**: HTML with poems
- **Implementation**: Scrape poem pages, extract notable lines

### 5. **Russian Philosophy Texts**
- **URL**: Various academic and digital library sites
- **Pros**: Deep, meaningful quotes from philosophers
- **Cons**: May be more academic, less "quotable"
- **Format**: PDF or HTML texts
- **Implementation**: Extract quotes from philosophy texts

### 6. **Russian Proverbs and Sayings**
- **URL**: Various collections
- **Pros**: Traditional wisdom, culturally rich
- **Cons**: May not have specific authors
- **Format**: Text collections
- **Implementation**: Load from curated collections

### 7. **Russian Literature Quotes (Project Gutenberg Russian)**
- **URL**: Project Gutenberg has some Russian texts
- **Pros**: Free, public domain
- **Cons**: Limited Russian collection
- **Format**: Plain text files
- **Implementation**: Similar to English Project Gutenberg

### 8. **Russian Quote Aggregators**
- **URL**: Various sites aggregating quotes
- **Pros**: Multiple sources in one place
- **Cons**: May have duplicates, variable quality
- **Format**: HTML
- **Implementation**: Scrape aggregated quote pages

## API-Based Sources

### 1. **Quotable API**
- **URL**: https://github.com/lukePeavey/quotable
- **Pros**: Free API, well-maintained, JSON format
- **Cons**: Limited to quotes in their database
- **Format**: JSON API
- **Implementation**: 
  ```python
  import requests
  response = requests.get('https://api.quotable.io/quotes?author=Einstein')
  ```

### 2. **They Said So API**
- **URL**: https://theysaidso.com/api
- **Pros**: Free tier available, good collection
- **Cons**: Rate limits on free tier
- **Format**: JSON API
- **Implementation**: Use API to fetch quotes by author/topic

### 3. **Forismatic API**
- **URL**: http://forismatic.com/en/api/
- **Pros**: Free API, multiple languages including Russian
- **Cons**: Random quotes, no specific author search
- **Format**: JSON/XML API
- **Implementation**: Fetch random quotes, filter by language

## Implementation Recommendations

### Priority 1: Easy to Integrate
1. **Goodreads Quotes** - Similar structure to WikiQuote
2. **BrainyQuote** - Large collection, good organization
3. **Афоризмы.ru** - Russian equivalent, similar structure

### Priority 2: High Quality
1. **Quote Investigator** - Verified quotes, high quality
2. **Project Gutenberg** - Extract from literature (more work but high quality)
3. **Poetry Foundation** - Curated poetry quotes

### Priority 3: API-Based (Easiest)
1. **Quotable API** - Free, JSON format
2. **Forismatic API** - Free, supports Russian
3. **They Said So API** - Good collection

## Implementation Strategy

### For Scraping-Based Sources:
```python
class GoodreadsScraper(BaseScraper):
    """Scraper for Goodreads quotes."""
    
    def scrape_author_quotes(self, author_name: str) -> List[str]:
        # Similar to WikiQuote scraper
        # Extract quotes from Goodreads author pages
        pass
```

### For API-Based Sources:
```python
def load_quotes_from_api(api_url: str, params: dict) -> List[dict]:
    """Load quotes from API source."""
    response = requests.get(api_url, params=params)
    data = response.json()
    quotes = []
    for item in data.get('results', []):
        if is_valid_quote(item['quote']):
            quotes.append({
                'text': item['quote'],
                'author': item.get('author'),
                'source': 'api_source'
            })
    return quotes
```

### For Text-Based Sources (Project Gutenberg):
```python
def extract_quotes_from_text(text: str, author: str) -> List[str]:
    """Extract quotes from full text using patterns."""
    quotes = []
    # Find text in quotation marks
    quoted_text = re.findall(r'"([^"]{30,})"', text)
    for quote in quoted_text:
        if is_valid_quote(quote):
            quotes.append(quote)
    return quotes
```

## Quality Considerations

1. **Validation**: Use existing `_is_valid_quote()` filters for all sources
2. **Deduplication**: Check against existing quotes before adding
3. **Attribution**: Ensure author information is preserved
4. **Source Tracking**: Track which source each quote came from
5. **Post-Load Cleanup**: Run cleanup script after loading from new sources

## Recommended Next Steps

1. **Start with API sources** (easiest):
   - Integrate Quotable API for English
   - Integrate Forismatic API for Russian
   - Add to existing loader

2. **Add scraping sources** (more quotes):
   - Goodreads scraper (English)
   - Афоризмы.ru scraper (Russian)
   - BrainyQuote scraper (English)

3. **Text extraction** (highest quality, most work):
   - Project Gutenberg integration
   - Extract quotes from literature texts
   - Lib.ru integration for Russian texts

## Notes

- All sources should use the same validation filters
- Track source in database for quality control
- Run cleanup script after loading from any new source
- Monitor for duplicates across sources
- Respect rate limits and terms of service

