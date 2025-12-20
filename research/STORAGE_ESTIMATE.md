# Storage and Loading Time Estimates

## WikiQuote Data Volume Estimates

### English WikiQuote (en.wikiquote.org)

**Authors:**
- Estimated total authors: **~5,000-8,000** notable authors
- Active authors with substantial quotes: **~2,000-3,000**

**Quotes per Author:**
- Average quotes per author: **20-50 quotes**
- Popular authors (Shakespeare, Wilde, etc.): **100-300 quotes**
- Total estimated quotes (EN): **~150,000 - 300,000 quotes**

### Russian WikiQuote (ru.wikiquote.org)

**Authors:**
- Estimated total authors: **~3,000-5,000** notable authors
- Active authors with substantial quotes: **~1,500-2,500**

**Quotes per Author:**
- Average quotes per author: **25-60 quotes** (Russian quotes tend to be longer)
- Popular authors (Пушкин, Достоевский, etc.): **150-400 quotes**
- Total estimated quotes (RU): **~100,000 - 250,000 quotes**

### Combined Total

- **Total Quotes (EN + RU):** ~250,000 - 550,000 quotes
- **Conservative Estimate:** ~400,000 quotes
- **Optimistic Estimate:** ~500,000 quotes

## Storage Size Calculation

### Per Quote Storage

Based on the database schema:

**Quote Table:**
- `id` (Integer): 4 bytes
- `text` (Text): Average 150 bytes (UTF-8, Russian may be longer)
- `author_id` (Integer): 4 bytes
- `source_id` (Integer): 4 bytes
- `language` (String(10)): 2-3 bytes
- `search_vector` (TSVECTOR): ~50-100 bytes (compressed)
- `created_at` (TIMESTAMP): 8 bytes
- **Row overhead:** ~24 bytes (PostgreSQL)
- **Total per quote:** ~240-260 bytes

**Author Table:**
- Average authors: ~4,000 (EN) + ~3,000 (RU) = ~7,000 authors
- Per author: ~300 bytes (name, bio, URL, timestamps)
- **Total authors:** ~2.1 MB

**Source Table:**
- Average sources: ~15,000 (EN) + ~12,000 (RU) = ~27,000 sources
- Per source: ~400 bytes (title, URL, metadata)
- **Total sources:** ~10.8 MB

**Quote Translations:**
- Estimated bilingual pairs: ~20,000 - 50,000 pairs
- Per translation link: ~20 bytes
- **Total translations:** ~0.4 - 1.0 MB

### Indexes and Overhead

**Full-Text Search Index (GIN):**
- `search_vector` GIN index: ~30-40% of text size
- For 400,000 quotes: ~18-24 MB

**Other Indexes:**
- Language index: ~2 MB
- Author index: ~1 MB
- Source index: ~2 MB
- **Total indexes:** ~23-29 MB

### Total Storage Estimate

**Raw Data:**
- Quotes (400,000 × 250 bytes): **~95 MB**
- Authors: **~2.1 MB**
- Sources: **~10.8 MB**
- Translations: **~0.7 MB**
- **Subtotal:** **~108.6 MB**

**Indexes:**
- Full-text search index: **~24 MB**
- Other indexes: **~5 MB**
- **Subtotal:** **~29 MB**

**PostgreSQL Overhead:**
- Table metadata, WAL, etc.: **~10-15%**
- **Subtotal:** **~15 MB**

**TOTAL ESTIMATED STORAGE:**
- **Conservative (400K quotes):** **~150-160 MB**
- **Realistic (500K quotes):** **~180-200 MB**
- **With growth margin:** **~250-300 MB recommended**

## Loading Time Estimates

### Scraping Time (Network-Bound)

**Factors:**
- WikiQuote rate limiting: ~1 request/second (configurable delay)
- Average quotes per page: ~30-50 quotes
- Pages to scrape: ~7,000 author pages + ~27,000 source pages = ~34,000 pages

**Scraping Calculation:**
- With 1 second delay: 34,000 pages × 1 second = **~9.4 hours**
- With 0.5 second delay: 34,000 pages × 0.5 seconds = **~4.7 hours**
- **Realistic estimate:** **6-10 hours** (with errors, retries, network issues)

**Optimization:**
- Parallel scraping (10 workers): **~1-2 hours** (but risk of rate limiting)
- Recommended: **2-3 workers** = **~3-5 hours**

### Database Insertion Time

**Factors:**
- Batch inserts vs. individual inserts
- PostgreSQL COPY command (fastest)
- Index creation (can be deferred)

**Insertion Rates:**
- Individual inserts: ~500-1,000 quotes/second
- Batch inserts (100 quotes/batch): ~2,000-3,000 quotes/second
- COPY command: ~5,000-10,000 quotes/second

**Time Calculation (400,000 quotes):**
- Individual inserts: 400,000 / 1,000 = **~6.7 minutes**
- Batch inserts: 400,000 / 2,500 = **~2.7 minutes**
- COPY command: 400,000 / 7,500 = **~0.9 minutes**

**Index Creation:**
- Full-text search index: **~2-5 minutes**
- Other indexes: **~1-2 minutes**
- **Total indexing:** **~3-7 minutes**

### Total Loading Time

**Scraping + Insertion:**
- Scraping: **6-10 hours** (network-bound)
- Database insertion: **~1-3 minutes** (very fast)
- Index creation: **~3-7 minutes**
- **Total:** **~6-10 hours** (scraping dominates)

**If Using Pre-Scraped Data:**
- Database insertion only: **~5-10 minutes**

## Recommendations

### Storage

1. **Initial Allocation:** Reserve **500 MB - 1 GB** for database
2. **Growth Margin:** Plan for 2-3x growth as you add more sources
3. **Backup Space:** Additional 500 MB for backups

### Performance Optimization

1. **Scraping:**
   - Use 2-3 parallel workers to balance speed and rate limits
   - Implement retry logic for failed requests
   - Cache pages locally to avoid re-scraping

2. **Database Loading:**
   - Use batch inserts (100-500 quotes per batch)
   - Defer index creation until after data load
   - Use `COPY` command for fastest insertion
   - Increase `maintenance_work_mem` for index creation

3. **Incremental Loading:**
   - Scrape authors incrementally (not all at once)
   - Track progress in `sources_metadata` table
   - Resume from last position on failure

### Example Optimized Loading Script

```python
# Pseudo-code for optimized loading
def optimized_load():
    # 1. Scrape in batches (100 authors at a time)
    # 2. Insert in batches (500 quotes per transaction)
    # 3. Create indexes after all data loaded
    # 4. Update search vectors in parallel
    
    # Estimated time: 4-6 hours (vs 6-10 hours sequential)
```

## Summary Table

| Metric | Conservative | Realistic | Notes |
|--------|-------------|-----------|-------|
| **Total Quotes** | 400,000 | 500,000 | EN + RU combined |
| **Database Size** | 150-160 MB | 180-200 MB | With indexes |
| **Scraping Time** | 6-8 hours | 8-10 hours | Network-bound |
| **Insertion Time** | 1-3 min | 1-3 min | Very fast |
| **Index Creation** | 3-5 min | 5-7 min | One-time |
| **Total Time** | 6-8 hours | 8-10 hours | Scraping dominates |

## Real-World Considerations

1. **Network Issues:** Add 20-30% buffer for retries and failures
2. **Rate Limiting:** WikiQuote may throttle aggressive scrapers
3. **Data Quality:** Some quotes may need cleaning/validation
4. **Translation Matching:** Additional time for matching bilingual pairs
5. **Hardware:** Faster CPU/SSD will improve insertion speed

## Conclusion

For a complete WikiQuote EN + RU dump:
- **Storage:** ~200-300 MB (with growth margin)
- **Time:** ~8-12 hours (mostly scraping, insertion is fast)
- **Recommendation:** Start with popular authors, expand incrementally

