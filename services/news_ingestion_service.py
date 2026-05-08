"""
Normalize and persist news from RSS, NewsAPI, scraping, or manual payloads.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from config import settings
from models import NewsArticle
from repositories.news_repository import NewsRepository
from logger_config import logger

_NEWS_API_URL = "https://newsapi.org/v2/top-headlines"
_REQUEST_TIMEOUT = 20

PROMINENT_NEWS_FEEDS: List[Dict[str, str]] = [
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "source": "rss:nytimes",
        "category": "general",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://feeds.npr.org/1001/rss.xml",
        "source": "rss:npr",
        "category": "general",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
        "source": "rss:nytimes-us",
        "category": "us",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
        "source": "rss:nytimes-politics",
        "category": "politics",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "source": "rss:nytimes-world",
        "category": "world",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml",
        "source": "rss:nytimes-europe",
        "category": "europe",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "source": "rss:nytimes-business",
        "category": "business",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "source": "rss:nytimes-tech",
        "category": "technology",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://www.technologyreview.com/feed/",
        "source": "rss:mit-tech-review",
        "category": "ai",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
        "source": "rss:nytimes-science",
        "category": "science",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
        "source": "rss:nytimes-health",
        "category": "health",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml",
        "source": "rss:nytimes-climate",
        "category": "nature",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml",
        "source": "rss:nytimes-arts",
        "category": "culture",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml",
        "source": "rss:nytimes-sports",
        "category": "sports",
        "language": "en",
        "country": "us",
    },
    {
        "url": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
        "source": "rss:rbc",
        "category": "russia",
        "language": "ru",
        "country": "ru",
    },
    {
        "url": "https://www.kommersant.ru/RSS/news.xml",
        "source": "rss:kommersant",
        "category": "russia",
        "language": "ru",
        "country": "ru",
    },
    {
        "url": "https://lenta.ru/rss/news",
        "source": "rss:lenta",
        "category": "russia",
        "language": "ru",
        "country": "ru",
    },
    {
        "url": "https://meduza.io/rss/all",
        "source": "rss:meduza",
        "category": "russia",
        "language": "ru",
        "country": "ru",
    },
    {
        "url": "https://www.kommersant.ru/RSS/section-business.xml",
        "source": "rss:kommersant-business",
        "category": "business",
        "language": "ru",
        "country": "ru",
    },
    {
        "url": "https://www.kommersant.ru/RSS/section-tech.xml",
        "source": "rss:kommersant-tech",
        "category": "technology",
        "language": "ru",
        "country": "ru",
    },
]


def _host_in_allowlist(host: str, allow: List[str]) -> bool:
    """Return True when host equals or is a subdomain of an allowed entry."""
    h = (host or "").lower().strip(".")
    for entry in allow:
        e = entry.lower().strip()
        if not e:
            continue
        if h == e or h.endswith("." + e):
            return True
    return False


def identify_breaking_news(
    title: str,
    content: str,
    keywords: List[str],
) -> bool:
    """Heuristic: title or body mentions configured urgent keywords."""
    if not keywords:
        return False
    blob = f"{title} {content}".lower()
    return any(k.lower() in blob for k in keywords if k.strip())


class NewsIngestionService:
    """Fetch RSS / NewsAPI / HTML and store as NewsArticle."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NewsRepository(db)

    def ingest_article(self, article_data: Dict[str, Any]) -> NewsArticle:
        """
        Insert or return existing article keyed by canonical URL.

        Args:
            article_data: Keys title, content, url, source, language,
                optional category, published_at (datetime or ISO str).

        Returns:
            NewsArticle ORM instance.
        """
        url = str(article_data["url"]).strip()
        found = self.db.query(NewsArticle).filter(
            NewsArticle.url == url
        ).first()
        if found:
            changed = False
            category = article_data.get("category")
            language = article_data.get("language")
            source = article_data.get("source")
            if category and found.category != category:
                found.category = str(category)[:80]
                changed = True
            if language and found.language != language:
                found.language = str(language)[:10]
                changed = True
            if source and found.source != source:
                found.source = str(source)[:100]
                changed = True
            if changed:
                self.db.add(found)
                self.db.commit()
                self.db.refresh(found)
            return found
        pub = article_data.get("published_at")
        if isinstance(pub, str):
            pub = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        return self.repo.create(
            title=str(article_data["title"]).strip()[:500],
            content=str(article_data["content"]).strip(),
            url=url[:1000],
            source=str(article_data.get("source", "manual"))[:100],
            published_at=pub,
            category=article_data.get("category"),
            language=str(article_data.get("language", "en"))[:10],
        )

    def fetch_from_rss(
        self,
        feed_url: str,
        *,
        category: Optional[str] = None,
        language: str = "en",
        source_label: Optional[str] = None,
        max_entries: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Parse RSS/Atom feed and return normalized dicts (not yet persisted).
        """
        parsed = feedparser.parse(feed_url)
        out: List[Dict[str, Any]] = []
        for entry in parsed.entries[:max_entries]:
            link = getattr(entry, "link", "") or ""
            title = getattr(entry, "title", "") or "(no title)"
            summary = getattr(entry, "summary", "") or getattr(
                entry, "description", ""
            ) or ""
            if not link:
                continue
            host = urlparse(link).netloc or "rss"
            out.append(
                {
                    "title": title,
                    "content": summary or title,
                    "url": link,
                    "source": source_label or f"rss:{host}",
                    "published_at": _parse_published(entry),
                    "category": category,
                    "language": language,
                }
            )
        logger.info("RSS %s parsed %s entries", feed_url, len(out))
        return out

    def ingest_rss_feed(
        self,
        feed_url: str,
        *,
        category: Optional[str] = None,
        language: str = "en",
        source_label: Optional[str] = None,
        max_entries: int = 50,
        published_after: Optional[datetime] = None,
    ) -> int:
        """Persist new articles from a feed URL."""
        count = 0
        rows = self.fetch_from_rss(
            feed_url,
            category=category,
            language=language,
            source_label=source_label,
            max_entries=max_entries,
        )
        for row in rows:
            pub = row.get("published_at")
            if published_after and pub and pub < published_after:
                continue
            exists = (
                self.db.query(NewsArticle)
                .filter(NewsArticle.url == row["url"])
                .first()
            )
            if exists:
                continue
            self.ingest_article(row)
            count += 1
        return count

    def ingest_prominent_recent_news(
        self,
        *,
        days: int = 30,
        limit_per_category: int = 100,
        countries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ingest curated RU/US feeds and keep newest rows per category.

        Feeds are RSS endpoints from prominent RU and US publishers. This
        favors recent prominent-site coverage, not social ranking.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        wanted = {c.lower() for c in countries or ["ru", "us"]}
        inserted = 0
        attempted = 0
        failures: List[Dict[str, str]] = []

        for feed in PROMINENT_NEWS_FEEDS:
            if feed["country"].lower() not in wanted:
                continue
            attempted += 1
            try:
                inserted += self.ingest_rss_feed(
                    feed["url"],
                    category=feed["category"],
                    language=feed["language"],
                    source_label=feed["source"],
                    max_entries=100,
                    published_after=cutoff,
                )
            except Exception as exc:
                logger.warning(
                    "Prominent feed failed %s: %s",
                    feed["url"],
                    exc,
                )
                failures.append({"url": feed["url"], "error": str(exc)[:200]})

        pruned = self.prune_categories(limit_per_category=limit_per_category)
        return {
            "attempted_feeds": attempted,
            "inserted": inserted,
            "pruned": pruned,
            "failures": failures,
        }

    def prune_categories(self, *, limit_per_category: int = 100) -> int:
        """Keep only newest rows per category; delete older generated data."""
        categories = [
            row[0]
            for row in self.db.query(NewsArticle.category).distinct().all()
            if row[0]
        ]
        deleted = 0
        for category in categories:
            rows = (
                self.db.query(NewsArticle)
                .filter(NewsArticle.category == category)
                .order_by(
                    NewsArticle.published_at.desc().nullslast(),
                    NewsArticle.created_at.desc(),
                    NewsArticle.id.desc(),
                )
                .offset(limit_per_category)
                .all()
            )
            for article in rows:
                self.db.delete(article)
                deleted += 1
        self.db.commit()
        return deleted

    def fetch_from_newsapi(
        self,
        category: Optional[str],
        *,
        language: str = "en",
        country: Optional[str] = None,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Pull headline rows from NewsAPI (top-headlines).

        Args:
            category: Optional NewsAPI category slug.
            language: UI language hint; maps to default country when needed.
            country: ISO 3166-1 alpha-2 override.
            page_size: Max articles (capped at 100).

        Returns:
            Normalized dict rows (empty when API key missing).
        """
        if not settings.news_api_key:
            logger.warning("news_api_key unset; skip NewsAPI fetch")
            return []
        params: Dict[str, Any] = {
            "apiKey": settings.news_api_key,
            "pageSize": min(max(page_size, 1), 100),
        }
        if country:
            params["country"] = country.lower()
        elif language.lower() == "ru":
            params["country"] = "ru"
        else:
            params["country"] = settings.news_api_country.lower()
        if category:
            params["category"] = category
        try:
            resp = requests.get(
                _NEWS_API_URL,
                params=params,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("NewsAPI request failed: %s", exc)
            return []
        payload = resp.json()
        articles = payload.get("articles") or []
        out: List[Dict[str, Any]] = []
        kws = settings.breaking_news_keywords
        for item in articles:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").strip()
            title = (item.get("title") or "").strip() or "(no title)"
            desc = (item.get("description") or "").strip()
            content = desc or title
            if not url or url == "null":
                continue
            src = item.get("source") or {}
            src_name = src.get("name") if isinstance(src, dict) else "newsapi"
            pub = item.get("publishedAt")
            published_at = None
            if isinstance(pub, str):
                try:
                    published_at = datetime.fromisoformat(
                        pub.replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = None
            cat = None
            if identify_breaking_news(title, content, list(kws)):
                cat = "breaking"
            elif category:
                cat = category
            out.append(
                {
                    "title": title[:500],
                    "content": content,
                    "url": url[:1000],
                    "source": f"newsapi:{src_name}"[:100],
                    "published_at": published_at,
                    "category": cat,
                    "language": language[:10],
                }
            )
        logger.info("NewsAPI returned %s normalized rows", len(out))
        return out

    def ingest_from_newsapi(
        self,
        category: Optional[str],
        *,
        language: str = "en",
        country: Optional[str] = None,
        page_size: int = 20,
    ) -> int:
        """Persist new articles from NewsAPI; returns insert count."""
        rows = self.fetch_from_newsapi(
            category,
            language=language,
            country=country,
            page_size=page_size,
        )
        count = 0
        for row in rows:
            exists = (
                self.db.query(NewsArticle)
                .filter(NewsArticle.url == row["url"])
                .first()
            )
            if exists:
                continue
            self.ingest_article(row)
            count += 1
        return count

    def fetch_article_page(self, page_url: str) -> Dict[str, Any]:
        """
        Download one HTTPS page from an allowlisted host.

        Raises:
            ValueError: scheme/host not permitted or fetch failed.
        """
        raw = page_url.strip()
        parsed = urlparse(raw)
        if parsed.scheme != "https":
            raise ValueError("only https URLs are supported for scraping")
        host = parsed.hostname
        if not host:
            raise ValueError("invalid URL")
        if not _host_in_allowlist(host, settings.news_scrape_allowed_hosts):
            raise ValueError(
                "host not in news_scrape_allowed_hosts; refusing fetch"
            )
        headers = {
            "User-Agent": (
                "AphoriumBot/1.0 (+https://github.com) news preview"
            ),
        }
        try:
            resp = requests.get(
                raw,
                timeout=_REQUEST_TIMEOUT,
                headers=headers,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"fetch failed: {exc}") from exc
        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.find("meta", property="og:title")
        title = ""
        if title_el and title_el.get("content"):
            title = title_el["content"].strip()
        if not title and soup.title and soup.title.string:
            title = soup.title.string.strip()
        if not title:
            title = "(no title)"
        desc_el = soup.find("meta", property="og:description")
        desc = ""
        if desc_el and desc_el.get("content"):
            desc = desc_el["content"].strip()
        chunks: List[str] = []
        for p in soup.find_all("p")[:40]:
            t = p.get_text(" ", strip=True)
            if len(t) > 60:
                chunks.append(t)
        body = "\n\n".join(chunks) if chunks else desc
        if not body:
            body = title
        return {
            "title": title[:500],
            "content": body,
            "url": raw[:1000],
            "source": f"scraped:{host}"[:100],
            "published_at": None,
            "category": None,
            "language": "en",
        }

    def scrape_news_site(self, site_url: str) -> List[Dict[str, Any]]:
        """
        Treat site_url as a single article page (allowlisted HTTPS only).

        Returns:
            One-element list of normalized dicts.
        """
        return [self.fetch_article_page(site_url)]

    def get_or_ingest_article_by_url(self, raw_url: str) -> NewsArticle:
        """Return existing row or scrape+insert when host is allowlisted."""
        u = raw_url.strip()
        found = self.db.query(NewsArticle).filter(
            NewsArticle.url == u
        ).first()
        if found:
            return found
        data = self.fetch_article_page(u)
        return self.ingest_article(data)


def _parse_published(entry: Any) -> Optional[datetime]:
    if getattr(entry, "published_parsed", None):
        t = entry.published_parsed
        return datetime(*t[:6])
    if getattr(entry, "updated_parsed", None):
        t = entry.updated_parsed
        return datetime(*t[:6])
    return None
