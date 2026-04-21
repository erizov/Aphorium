"""
Periodic RSS / NewsAPI ingestion (separate DB session per cycle).
"""

from config import settings
from database import SessionLocal
from logger_config import logger
from services.news_ingestion_service import NewsIngestionService


def run_news_ingestion_cycle() -> None:
    """Ingest configured RSS feeds and optional NewsAPI headlines."""
    db = SessionLocal()
    try:
        svc = NewsIngestionService(db)
        for feed in settings.rss_feeds:
            url = feed.strip()
            if not url:
                continue
            try:
                inserted = svc.ingest_rss_feed(url)
                if inserted:
                    logger.info("RSS %s inserted %s rows", url, inserted)
            except Exception as exc:
                logger.warning("RSS ingest failed %s: %s", url, exc)
        if settings.news_api_key:
            try:
                inserted = svc.ingest_from_newsapi(
                    category=None,
                    language="en",
                    page_size=30,
                )
                if inserted:
                    logger.info("NewsAPI inserted %s rows", inserted)
            except Exception as exc:
                logger.warning("NewsAPI ingest failed: %s", exc)
    finally:
        db.close()
