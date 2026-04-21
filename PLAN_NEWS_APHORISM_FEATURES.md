# News-to-Aphorism Features Implementation Plan

> **Status**: Saved for future implementation  
> **Created**: 2026-01-24  
> **Next Steps**: Review this plan when ready to implement news-to-aphorism features

## Overview

This plan implements three interconnected features that bridge news and aphorisms:
1. **Breaking News Notification Service**: Transforms urgent news alerts into memorable aphorism-style one-liners
2. **Aphorism-News Pairing Database**: Links historical aphorisms with relevant current news stories
3. **AI Aphoristic Summary Generator**: Analyzes news articles and generates concise, shareable aphoristic summaries

## Architecture Overview

```
News Sources (RSS/API/Scraping) 
    ↓
News Ingestion Service
    ↓
┌─────────────────────────────────────┐
│  AI Processing Service (OpenAI)     │
│  - Transform breaking news          │
│  - Generate aphoristic summaries    │
│  - Match news to aphorisms          │
└─────────────────────────────────────┘
    ↓
Database (New Tables)
    ↓
API Endpoints + WebSocket
    ↓
Frontend (React)
```

## Database Schema Changes

### New Tables

**`news_articles`** - Stores ingested news articles
- `id` (Integer, PK)
- `title` (String, required)
- `content` (Text, required)
- `url` (String, unique, indexed)
- `source` (String) - e.g., 'newsapi', 'rss', 'scraped'
- `published_at` (TIMESTAMP)
- `category` (String) - e.g., 'breaking', 'politics', 'technology'
- `language` (String) - 'en' or 'ru'
- `created_at` (TIMESTAMP)
- `processed_at` (TIMESTAMP, nullable) - when AI processing completed

**`news_aphorisms`** - AI-generated aphorism versions of news
- `id` (Integer, PK)
- `news_article_id` (Integer, FK to news_articles)
- `aphorism_text` (Text, required) - the aphorism-style version
- `language` (String) - 'en' or 'ru'
- `generation_method` (String) - 'breaking_alert' or 'summary'
- `created_at` (TIMESTAMP)

**`aphorism_news_pairs`** - Links existing quotes to relevant news
- `id` (Integer, PK)
- `quote_id` (Integer, FK to quotes)
- `news_article_id` (Integer, FK to news_articles)
- `relevance_score` (Integer, 0-100) - AI-generated relevance
- `match_reason` (Text) - why they're paired
- `created_at` (TIMESTAMP)
- Unique constraint on (quote_id, news_article_id)

**`news_notifications`** - Tracks sent notifications
- `id` (Integer, PK)
- `news_aphorism_id` (Integer, FK to news_aphorisms)
- `delivery_method` (String) - 'websocket', 'api'
- `delivered_at` (TIMESTAMP)
- `recipient_id` (String, nullable) - for future user targeting

## Implementation Components

### 1. News Ingestion Layer

**Location**: `services/news_ingestion_service.py`

**Responsibilities**:
- Fetch news from multiple sources (News API, RSS feeds, web scraping)
- Normalize news articles into common format
- Store in `news_articles` table
- Filter and categorize breaking news

**Key Methods**:
- `fetch_from_newsapi(category: str, language: str) -> List[dict]`
- `fetch_from_rss(feed_url: str) -> List[dict]`
- `scrape_news_site(site_url: str) -> List[dict]`
- `ingest_article(article_data: dict) -> NewsArticle`
- `identify_breaking_news(article: NewsArticle) -> bool`

**Dependencies**: 
- `feedparser` for RSS parsing
- `requests` + `beautifulsoup4` for scraping
- News API client library

### 2. AI Processing Service

**Location**: `services/ai_aphorism_service.py`

**Responsibilities**:
- Transform breaking news into aphorism format using OpenAI
- Generate aphoristic summaries from full articles
- Match news articles to relevant existing aphorisms
- Handle rate limiting and error recovery

**Key Methods**:
- `transform_to_aphorism(news_text: str, context: dict) -> str`
- `generate_aphoristic_summary(article: NewsArticle) -> str`
- `find_relevant_aphorisms(news_article: NewsArticle, limit: int = 5) -> List[dict]`
- `_call_openai(prompt: str, max_tokens: int) -> str`

**OpenAI Integration**:
- Use `openai` Python library
- Configure API key via `config.py`
- Implement retry logic with exponential backoff
- Cache prompts for common patterns

**Prompt Engineering**:
- Breaking news: "Transform this breaking news into a memorable one-liner aphorism that captures both the facts and broader significance. Make it digestible and less anxiety-inducing."
- Summary: "Summarize this news article as a concise aphorism suitable for social media sharing. Capture the key point in a memorable, quotable format."
- Matching: "Find historical aphorisms from our database that relate to this news story. Explain why each aphorism is relevant."

### 3. Notification Service

**Location**: `services/notification_service.py`

**Responsibilities**:
- Queue breaking news aphorisms for delivery
- Manage WebSocket connections
- Broadcast notifications to connected clients
- Track delivery status

**Key Methods**:
- `send_breaking_news_aphorism(aphorism: NewsAphorism) -> None`
- `broadcast_to_websocket(message: dict) -> None`
- `register_websocket_connection(websocket: WebSocket) -> None`
- `unregister_websocket_connection(websocket: WebSocket) -> None`

**WebSocket Implementation**:
- Use FastAPI's WebSocket support
- Maintain connection pool in memory (or Redis for scaling)
- Send JSON messages: `{"type": "breaking_news", "aphorism": "...", "original_news": {...}}`

### 4. Repository Layer

**New Files**:
- `repositories/news_repository.py` - CRUD for news articles
- `repositories/news_aphorism_repository.py` - CRUD for generated aphorisms
- `repositories/aphorism_news_pair_repository.py` - CRUD for pairings

**Pattern**: Follow existing repository pattern from `repositories/quote_repository.py`

### 5. API Routes

**New File**: `api/routes/news.py`

**Endpoints**:
- `GET /api/news/articles` - List news articles (with pagination, filtering)
- `GET /api/news/articles/{id}` - Get single article with nested aphorisms and related quotes (see **API payloads for UI** below)
- `GET /api/news/breaking` - Get recent breaking news aphorisms
- `GET /api/news/{article_id}/aphorisms` - Get aphorisms for article
- `GET /api/news/{article_id}/related-quotes` - Get paired historical aphorisms
- `POST /api/news/summarize` - Generate aphoristic summary for article (by URL or ID)
- `GET /api/news/pairs` - Search aphorism-news pairs
- `WS /api/news/notifications` - WebSocket endpoint for real-time notifications

**API payloads for UI** (so the frontend can render news + aphorisms + authors without N+1 requests):

- **List** `GET /api/news/articles`: each item includes `title`, `url`, `source`, `published_at`, `category`, `language`, optional short `content_preview`, plus:
  - `aphorisms`: array (often 0–1 for feed) of `{ id, aphorism_text, generation_method, language }`
  - `related_quotes`: capped list (e.g. top 3) of `{ relevance_score, match_reason, quote: { id, text, language }, author: { id, name_en, name_ru } | null, source: { id, title, language } | null }`
- **Detail** `GET /api/news/articles/{id}`: full `content`, **all** `aphorisms`, **all** `related_quotes` with the same nested shape (author/source nullable when missing in DB).

Author display: pick `name_en` vs `name_ru` from `article.language` or user UI language; show "Unknown author" when `author` is null.

### 6. Background Tasks

**New File**: `services/news_processor.py`

**Responsibilities**:
- Periodic news fetching (scheduled task)
- Process new articles through AI pipeline
- Match articles to existing aphorisms
- Generate and queue breaking news notifications

**Scheduling**:
- Use `asyncio` + `schedule` or `celery` for background tasks
- Configurable intervals via `config.py`
- Run as separate process or FastAPI background task

### 7. Configuration Updates

**File**: `config.py`

**New Settings**:
- `openai_api_key: Optional[str]` - OpenAI API key
- `openai_model: str = "gpt-4"` - Model to use
- `news_api_key: Optional[str]` - NewsAPI.org key
- `news_fetch_interval: int = 300` - Seconds between news fetches
- `rss_feeds: List[str]` - List of RSS feed URLs
- `news_scrape_sites: List[str]` - Sites to scrape
- `breaking_news_keywords: List[str]` - Keywords to identify breaking news
- `websocket_enabled: bool = True`

### 8. Frontend Updates — News + aphorisms + authors

**Stack**: Match the existing app ([`frontend/src/App.jsx`](frontend/src/App.jsx)): React, MUI (`Card`, `Grid`, `Typography`, `Chip`, `Dialog`, `Snackbar`), `axios` against `API_BASE = '/api'`.

**Visual design — Apple-style typography and palette**

- **Typography**: Use Apple’s system stack so text matches macOS/iOS feel: `-apple-system`, `BlinkMacSystemFont`, `"SF Pro Text"`, `"SF Pro Display"`, then `Segoe UI`, `Roboto`, `Helvetica Neue`, `Arial`, sans-serif. Wire via MUI `createTheme({ typography: { fontFamily: … } })` (and optional `fontFamily` overrides for `h4` / quote blocks). Prefer regular/medium weights; avoid decorative webfonts unless later localized branding requires them.
- **Light palette** (HIG-aligned approximations): page/grouped background `#F2F2F7`, elevated cards `#FFFFFF`, primary label `#000000`, secondary label `rgba(60, 60, 67, 0.6)`, tertiary/muted `rgba(60, 60, 67, 0.3)`, dividers `rgba(60, 60, 67, 0.12)`, **accent / links / primary actions** `#007AFF` (system blue). Chips for category/relevance use light gray fills (`#E5E5EA`) with dark text, not loud saturated colors unless `breaking` needs a single red/destructive tone (`#FF3B30`).
- **Dark palette**: background `#000000`, elevated surfaces `#1C1C1E`, primary label `#FFFFFF`, secondary `rgba(235, 235, 245, 0.6)`, accent `#0A84FF`, dividers `rgba(84, 84, 88, 0.65)`.
- **Shape / density**: Card radius ~12px, comfortable padding (16–20px), generous whitespace between headline, aphorism, and archive list—Apple-like rhythm over dense dashboards.
- **Scope**: Implement these tokens in `frontend/src/theme/appleMuiTheme.js` and use them **app-wide**: replace the existing **purple gradient** `lightTheme` / `darkTheme` in [`App.jsx`](frontend/src/App.jsx) with Apple HIG-style light/dark themes from that module. A **single** root `ThemeProvider` (already wrapping the app) switches mode between the two Apple themes so the **quote browser and News hub share one visual system** at launch—no staged “News only” theme.

**Primary experience — “News hub”** (new top-level section or route, e.g. tab **News** next to the main quote browser):

1. **Toolbar**: language toggle (reuse existing EN/RU pattern), optional category `Chip`s (`breaking`, `politics`, …), text search over title/content, refresh button.
2. **Feed layout**: responsive `Grid` of **story cards**. Each card is one current news row with everything visible at a glance:
   - **Headline block**: `title` (link opens original `url` in new tab), metadata row: `source`, formatted `published_at`, `category` as small chips.
   - **Generated aphorism block** (prominent quote typography): latest or preferred `aphorisms[]` entry (`aphorism_text`); subtitle shows `generation_method` (`breaking_alert` vs `summary`) as a muted chip.
   - **“From the archive” block**: `related_quotes` as a compact `List` — each row shows **quote `text`**, then a secondary line **author** (`name_en` / `name_ru` by UI language) and, if present, **source** `title` in lighter type; trailing **relevance** `Chip` (e.g. score /100). Optional `Tooltip` or `IconButton` with `InfoOutlined` to reveal `match_reason` without cluttering the card.
   - **Empty related list**: copy like “No matched aphorisms yet” (pairing job not run or no hits).
3. **Detail**: clicking “Expand” or the card body opens a **full-screen `Dialog` or dedicated route** with full `content` (collapsible long text), **all** aphorisms, and **all** related quotes in an `Accordion` per quote (header = author + score; body = quote + `match_reason`). Reuse [`TextToSpeechButton`](frontend/src/components/TextToSpeechButton.jsx) on generated aphorisms and on archive quotes where useful.
4. **Realtime**: `WS /api/news/notifications` pushes new breaking items — surface as **Snackbar** / top **Alert** (same pattern as existing `Snackbar` in `App.jsx`) plus optional **drawer** listing last N events; each toast can deep-link into the hub with that `article_id` highlighted.
5. **Extras** (Phase 3+): dedicated **Pairs explorer** (table or list from `GET /api/news/pairs`); **Summarize** panel (paste URL or body → `POST /api/news/summarize`) showing returned aphorism + link to stored article.

**New / renamed components** (split from monolith over time):

- `NewsHub.jsx` — fetches list endpoint, holds filters, pagination state.
- `NewsStoryCard.jsx` — single card (headline + aphorism + `RelatedQuoteRow` list).
- `RelatedQuoteRow.jsx` — one historical quote + author + optional source + relevance.
- `NewsArticleDetail.jsx` — dialog or page for detail payload.
- `NewsNotifications.jsx` — WS subscription + snackbar/drawer wiring.
- (Optional) `BreakingNewsPanel.jsx` — narrow strip of latest breaking-only cards.

**Loading / errors**: `CircularProgress` center while fetching; `Alert` severity error on failed load; skeleton cards optional for polish.

## Implementation Order

### Phase 1: Foundation
1. Create database models and migrations
2. Set up OpenAI integration and configuration
3. Create repository layer for news data
4. Implement basic news ingestion (News API first)

### Phase 2: Core Features
5. Implement AI aphorism transformation service
6. Create news processing pipeline
7. Build API endpoints for news and aphorisms
8. Implement WebSocket notification system

### Phase 3: Advanced Features
9. Add RSS feed support
10. Add web scraping capability
11. Implement aphorism-news pairing logic
12. Build frontend components **and** switch global MUI theme to Apple palette/fonts (quote UI + News together)

### Phase 4: Polish
13. Add error handling and retry logic
14. Implement caching for AI responses
15. Add monitoring and logging
16. Write tests for critical paths

## Key Files to Create/Modify

**New Files**:
- `models.py` - Add NewsArticle, NewsAphorism, AphorismNewsPair, NewsNotification models
- `services/news_ingestion_service.py`
- `services/ai_aphorism_service.py`
- `services/notification_service.py`
- `services/news_processor.py`
- `repositories/news_repository.py`
- `repositories/news_aphorism_repository.py`
- `repositories/aphorism_news_pair_repository.py`
- `api/routes/news.py`
- `alembic/versions/XXXX_add_news_tables.py` - Database migration
- `frontend/src/components/NewsHub.jsx`
- `frontend/src/components/NewsStoryCard.jsx`
- `frontend/src/components/RelatedQuoteRow.jsx`
- `frontend/src/components/NewsArticleDetail.jsx`
- `frontend/src/components/NewsNotifications.jsx`
- `frontend/src/components/BreakingNewsPanel.jsx` (optional strip)
- `frontend/src/theme/appleMuiTheme.js` — `createAppleLightTheme()` / `createAppleDarkTheme()` (or one factory with `palette.mode`) exporting MUI themes for the **entire** app

**Modified Files**:
- `config.py` - Add OpenAI and news-related settings
- `api/main.py` - Include news router, add WebSocket support
- `requirements.txt` - Add `openai`, `feedparser`, `schedule` (or `celery`)
- `frontend/src/App.jsx` - **Migrate** root theming to `appleMuiTheme.js` (remove purple `#667eea` / `#764ba2` primaries); add News hub entry (tab/route), wire WebSocket for notifications

## Dependencies to Add

```python
openai>=1.0.0          # OpenAI API client
feedparser>=6.0.10     # RSS feed parsing
schedule>=1.2.0        # Task scheduling (or celery for production)
websockets>=12.0       # WebSocket support (if not using FastAPI's built-in)
```

## Error Handling Strategy

- **OpenAI API**: Retry with exponential backoff, fallback to simpler prompts
- **News Sources**: Graceful degradation if one source fails
- **WebSocket**: Auto-reconnect logic in frontend
- **Database**: Transaction rollback on errors, log failures

## Performance Considerations

- Cache AI-generated aphorisms to avoid regenerating for same article
- Batch process news articles (not one-by-one)
- Use database indexes on `news_articles.url`, `published_at`, `category`
- Rate limit OpenAI API calls to stay within budget
- Consider Redis for WebSocket connection management at scale

## Testing Strategy

- Unit tests for AI prompt generation
- Integration tests for news ingestion
- E2E tests for WebSocket notifications
- Mock OpenAI API responses in tests
- Test aphorism-news matching algorithm

## Security Considerations

- Validate and sanitize all news article content
- Rate limit API endpoints
- Secure WebSocket connections (WSS in production)
- Store API keys securely (environment variables, not in code)
- Validate RSS feed URLs and scrape targets to prevent SSRF

## Implementation Checklist

- [ ] Create database models for news_articles, news_aphorisms, aphorism_news_pairs, and news_notifications tables
- [ ] Create Alembic migration script for new news-related tables
- [ ] Add OpenAI API key, News API key, and news-related configuration settings to config.py
- [ ] Create repository layer: news_repository.py, news_aphorism_repository.py, aphorism_news_pair_repository.py
- [ ] Implement news_ingestion_service.py with News API, RSS, and web scraping support
- [ ] Implement ai_aphorism_service.py with OpenAI integration for transforming news to aphorisms
- [ ] Implement notification_service.py with WebSocket support for real-time breaking news alerts
- [ ] Create news_processor.py background task for periodic news fetching and AI processing
- [ ] Create api/routes/news.py with endpoints for news articles, aphorisms, pairs, and WebSocket notifications
- [ ] Integrate WebSocket support in api/main.py and implement connection management
- [ ] Create React components: NewsHub, NewsStoryCard, RelatedQuoteRow, NewsArticleDetail, NewsNotifications (optional BreakingNewsPanel)
- [ ] Add `appleMuiTheme.js` and wire **root** `ThemeProvider` in `App.jsx` so **quote browser + News** both use Apple fonts/palette; delete in-file purple themes
- [ ] Integrate News hub and WebSocket notifications into `App.jsx`; ensure list/detail API returns nested author/source for quotes
- [ ] Update requirements.txt with openai, feedparser, schedule, and websockets packages
- [ ] Add comprehensive error handling, retry logic, and logging throughout news services
- [ ] Write unit tests for AI service, integration tests for news ingestion, and E2E tests for WebSocket notifications
