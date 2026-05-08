"""News ingestion helpers and NewsAPI shaping."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from config import settings
from models import NewsArticle
from repositories.news_repository import NewsRepository
from services.news_ingestion_service import (
    NewsIngestionService,
    _sort_rows_newest_first,
    identify_breaking_news,
)


def test_sort_rows_newest_first_orders_and_trailing_undated():
    old = {"published_at": datetime(2020, 1, 1), "id": "a"}
    new = {"published_at": datetime(2024, 6, 1), "id": "b"}
    nodate = {"published_at": None, "id": "c"}
    got = _sort_rows_newest_first([old, nodate, new])
    assert [r["id"] for r in got] == ["b", "a", "c"]


def test_identify_breaking_news_respects_keywords():
    assert identify_breaking_news("Hi", "there", []) is False
    assert identify_breaking_news(
        "BREAKING: storm",
        "details",
        ["breaking"],
    ) is True
    assert identify_breaking_news(
        "Calm headline",
        "no urgency",
        ["breaking"],
    ) is False


def test_fetch_from_newsapi_requires_key(monkeypatch, db_session):
    monkeypatch.setattr(settings, "news_api_key", None)
    svc = NewsIngestionService(db_session)
    assert svc.fetch_from_newsapi(None, language="en") == []


def test_fetch_from_newsapi_normalizes(monkeypatch, db_session):
    monkeypatch.setattr(settings, "news_api_key", "test-key")
    monkeypatch.setattr(settings, "news_api_country", "us")
    monkeypatch.setattr(settings, "breaking_news_keywords", ["urgent"])

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "articles": [
            {
                "title": "Urgent update on markets",
                "description": "Stocks move.",
                "url": "https://news.example/a1",
                "publishedAt": "2024-01-02T12:00:00Z",
                "source": {"name": "Demo"},
            },
            {"title": "bad", "url": "", "description": ""},
        ],
    }
    mock_resp.raise_for_status = MagicMock()

    def fake_get(url, params=None, timeout=None):
        assert "top-headlines" in url
        assert params["apiKey"] == "test-key"
        return mock_resp

    monkeypatch.setattr(
        "services.news_ingestion_service.requests.get",
        fake_get,
    )
    svc = NewsIngestionService(db_session)
    rows = svc.fetch_from_newsapi("technology", language="en", page_size=5)
    assert len(rows) == 1
    assert rows[0]["url"].startswith("https://news.example")
    assert rows[0]["category"] == "breaking"
    assert rows[0]["source"].startswith("newsapi:")


def test_ingest_from_newsapi_inserts_once(monkeypatch, db_session):
    monkeypatch.setattr(settings, "news_api_key", "k")
    monkeypatch.setattr(settings, "breaking_news_keywords", [])

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "articles": [
            {
                "title": "T1",
                "description": "D1",
                "url": "https://unique.example/u1",
                "source": {"name": "S"},
            },
        ],
    }
    mock_resp.raise_for_status = MagicMock()
    monkeypatch.setattr(
        "services.news_ingestion_service.requests.get",
        lambda *a, **k: mock_resp,
    )
    svc = NewsIngestionService(db_session)
    assert svc.ingest_from_newsapi("science", page_size=5) == 1
    assert svc.ingest_from_newsapi("science", page_size=5) == 0


def test_scrape_refuses_non_https(monkeypatch, db_session):
    monkeypatch.setattr(
        settings,
        "news_scrape_allowed_hosts",
        ["example.com"],
    )
    svc = NewsIngestionService(db_session)
    with pytest.raises(ValueError, match="https"):
        svc.fetch_article_page("http://example.com/x")


def test_scrape_refuses_unknown_host(monkeypatch, db_session):
    monkeypatch.setattr(
        settings,
        "news_scrape_allowed_hosts",
        ["safe.example"],
    )
    svc = NewsIngestionService(db_session)
    with pytest.raises(ValueError, match="news_scrape_allowed_hosts"):
        svc.fetch_article_page("https://evil.com/x")


def test_get_or_ingest_uses_existing_row(db_session):
    repo = NewsRepository(db_session)
    art = repo.create(
        title="Old",
        content="Body",
        url="https://example.com/existing",
        source="unit",
        language="en",
    )
    svc = NewsIngestionService(db_session)
    again = svc.get_or_ingest_article_by_url("https://example.com/existing")
    assert again.id == art.id


def test_prominent_recent_ingest_filters_old_rows(monkeypatch, db_session):
    svc = NewsIngestionService(db_session)

    def fake_fetch(*args, **kwargs):
        return [
            {
                "title": "Fresh",
                "content": "Fresh body",
                "url": "https://news.example/fresh",
                "source": "rss:test",
                "published_at": datetime.utcnow(),
                "category": kwargs["category"],
                "language": kwargs["language"],
            },
            {
                "title": "Old",
                "content": "Old body",
                "url": "https://news.example/old",
                "source": "rss:test",
                "published_at": datetime(2000, 1, 1),
                "category": kwargs["category"],
                "language": kwargs["language"],
            },
        ]

    monkeypatch.setattr(svc, "fetch_from_rss", fake_fetch)
    monkeypatch.setattr(
        "services.news_ingestion_service.PROMINENT_NEWS_FEEDS",
        [
            {
                "url": "https://feed.example/rss",
                "source": "rss:test",
                "category": "general",
                "language": "en",
                "country": "us",
            },
        ],
    )

    result = svc.ingest_prominent_recent_news(
        days=30,
        limit_per_category=100,
        countries=["us"],
    )

    rows = db_session.query(NewsArticle).all()
    assert result["inserted"] == 1
    assert len(rows) == 1
    assert rows[0].title == "Fresh"


def test_prune_categories_keeps_newest_100(db_session):
    repo = NewsRepository(db_session)
    for idx in range(105):
        repo.create(
            title=f"Article {idx}",
            content="Body",
            url=f"https://example.com/article-{idx}",
            source="unit",
            published_at=datetime(2024, 1, 1, 0, idx % 60),
            category="general",
            language="en",
        )

    svc = NewsIngestionService(db_session)
    deleted = svc.prune_categories(limit_per_category=100)
    remaining = db_session.query(NewsArticle).filter_by(
        category="general",
    ).count()

    assert deleted == 5
    assert remaining == 100
