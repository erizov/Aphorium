# Search Behavior Documentation

## How Search Works

### 1. Query Processing

**Input:** User enters a search query (e.g., "love", "a love is", '"a love is"')

**Processing:**
1. **Sanitization:** Query is sanitized to prevent SQL injection
2. **Quote Stripping:** If query is wrapped in quotes (`"a love is"`), quotes are stripped
3. **Translation:** Query is translated to the other language (EN->RU or RU->EN)
4. **Search:** Both original and translated queries are used to search

### 2. Search Strategies

#### PostgreSQL (Full-Text Search)
- Uses `plainto_tsquery()` which:
  - Treats multi-word queries as **phrases** (words must appear in order)
  - Automatically handles special characters
  - Matches words in the order they appear in the query

#### SQLite (LIKE Search)
- Uses `LIKE '%query%'` pattern matching
- Matches the phrase as a substring

### 3. Why Quoted Searches Return Fewer Results

**Problem:** When users search with quotes like `"a love is"`, they might expect exact phrase matching, but:

1. **Quote Stripping:** The system strips quotes to allow phrase matching
2. **Phrase Matching:** `plainto_tsquery` matches words in order, which is stricter than individual word matching
3. **Exact Phrase:** If the exact phrase doesn't exist in the database, no results are returned

**Example:**
- Query: `"a love is"`
- Stripped to: `a love is`
- Matches: Quotes containing "a love is" in that exact order
- Does NOT match: "love is a", "a love", "love is"

### 4. Should You Use Quotes for Phrase Search?

**Answer: Yes, but quotes are optional!**

**How it works:**
- **With quotes:** `"a love is"` → Stripped to `a love is` → Matches phrase in order
- **Without quotes:** `a love is` → Matches phrase in order (same result)

**Both work the same way!** The system treats multi-word queries as phrases regardless of quotes.

**When to use quotes:**
- **Optional:** Use quotes if you want to be explicit about phrase search
- **Not required:** Multi-word queries are automatically treated as phrases
- **Helpful:** Quotes make it clear you're searching for a phrase

### 5. Search Tips

1. **Single word:** `love` → Matches any quote containing "love"
2. **Multiple words:** `a love is` → Matches quotes with "a love is" in that order
3. **With quotes:** `"a love is"` → Same as above (quotes are stripped)
4. **Mixed languages:** `love` → Also searches for "любовь" (translated)

### 6. Improving Search Results

**If you're getting fewer results than expected:**

1. **Try without quotes:** `a love is` instead of `"a love is"`
2. **Try individual words:** `love` instead of `a love is`
3. **Check spelling:** Make sure words are spelled correctly
4. **Try translation:** Search in the other language (e.g., "любовь" instead of "love")

**The system automatically:**
- Translates your query to search in both languages
- Matches phrases when words appear in order
- Handles special characters automatically

