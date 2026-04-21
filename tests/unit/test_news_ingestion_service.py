"""News ingestion helpers and NewsAPI shaping."""

from unittest.mock import MagicMock

import pytest

from config import settings
from repositories.news_repository import NewsRepository
from services.news_ingestion_service import (
    NewsIngestionService,
    identify_breaking_news,
)


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
    monkeypatch.setattr(settings, "news_scrape_allowed_hosts", ["example.com"])
    svc = NewsIngestionService(db_session)
    with pytest.raises(ValueError, match="https"):
        svc.fetch_article_page("http://example.com/x")


def test_scrape_refuses_unknown_host(monkeypatch, db_session):
    monkeypatch.setattr(settings, "news_scrape_allowed_hosts", ["safe.example"])
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
