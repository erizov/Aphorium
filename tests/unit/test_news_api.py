"""HTTP surface for news routes (SQLite + dependency override)."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from config import settings
from database import get_db
from repositories.news_repository import NewsRepository


@pytest.fixture
def api_client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_summarize_validation_requires_one_target(api_client):
    r = api_client.post("/api/news/summarize", json={})
    assert r.status_code == 422
    r2 = api_client.post(
        "/api/news/summarize",
        json={"article_id": 1, "url": "https://a.com"},
    )
    assert r2.status_code == 422


def test_summarize_by_article_id(api_client, db_session, monkeypatch):
    monkeypatch.setattr(
        "services.ai_aphorism_service.chat_complete",
        lambda *a, **k: "Tiny summary.",
    )
    art = NewsRepository(db_session).create(
        title="T",
        content="Long body " * 20,
        url="https://example.com/sum-1",
        source="unit",
        language="en",
    )
    r = api_client.post(
        "/api/news/summarize",
        json={"article_id": art.id},
    )
    assert r.status_code == 200
    assert r.json()["aphorism_text"] == "Tiny summary."


def test_summarize_by_url_scrape(api_client, monkeypatch):
    monkeypatch.setattr(settings, "news_scrape_allowed_hosts", ["example.com"])
    monkeypatch.setattr(
        "services.ai_aphorism_service.chat_complete",
        lambda *a, **k: "URL summary.",
    )

    class Resp:
        text = (
            "<html><head><title>Page</title></head><body>"
            "<p>" + ("word " * 40) + "</p></body></html>"
        )

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "services.news_ingestion_service.requests.get",
        lambda *a, **k: Resp(),
    )
    r = api_client.post(
        "/api/news/summarize",
        json={"url": "https://example.com/article-z"},
    )
    assert r.status_code == 200
    assert r.json()["aphorism_text"] == "URL summary."


def test_ingest_newsapi_without_key(api_client, monkeypatch):
    monkeypatch.setattr(settings, "news_api_key", None)
    r = api_client.post("/api/news/ingest-newsapi", json={})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_news_ws_manager_broadcast():
    from services.notification_service import NewsWebSocketManager

    class FakeWs:
        def __init__(self) -> None:
            self.sent: list = []

        async def accept(self) -> None:
            return None

        async def send_json(self, data: dict) -> None:
            self.sent.append(data)

    mgr = NewsWebSocketManager()
    ws = FakeWs()
    await mgr.connect(ws)
    assert len(mgr._connections) == 1
    await mgr.broadcast({"type": "ping"})
    assert ws.sent == [{"type": "ping"}]
    mgr.disconnect(ws)
    assert not mgr._connections
