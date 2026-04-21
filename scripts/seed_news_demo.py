"""
Insert sample news rows for local UI testing (no LLM required).

Run from project root:
    python scripts/seed_news_demo.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect  # noqa: E402

from database import SessionLocal, engine, init_db  # noqa: E402
from models import NewsArticle, Quote  # noqa: E402
from repositories.news_repository import NewsRepository  # noqa: E402
from repositories.news_aphorism_repository import (  # noqa: E402
    NewsAphorismRepository,
)
from repositories.aphorism_news_pair_repository import (  # noqa: E402
    AphorismNewsPairRepository,
)
from logger_config import logger  # noqa: E402


def _ensure_news_tables() -> None:
    """Create news tables when DB was set up without Alembic."""
    insp = inspect(engine)
    if not insp.has_table("news_articles"):
        logger.info(
            "Table news_articles missing; running init_db() "
            "(SQLAlchemy create_all)."
        )
        init_db()


def main() -> None:
    _ensure_news_tables()
    db = SessionLocal()
    try:
        repo = NewsRepository(db)
        aph_repo = NewsAphorismRepository(db)
        pair_repo = AphorismNewsPairRepository(db)

        samples = [
            {
                "title": "Markets pause as leaders debate the future of work",
                "content": (
                    "Global indexes were mixed Monday as policymakers discussed "
                    "labor reforms, automation, and shorter work weeks."
                ),
                "url": "https://example.com/news/demo-markets-work",
                "source": "demo",
                "category": "breaking",
                "language": "en",
            },
            {
                "title": "Quiet courage: communities rebuild after the storm",
                "content": (
                    "Volunteers coordinated relief efforts while engineers "
                    "restored power to coastal towns."
                ),
                "url": "https://example.com/news/demo-storm-rebuild",
                "source": "demo",
                "category": "politics",
                "language": "en",
            },
        ]

        for row in samples:
            exists = (
                db.query(NewsArticle)
                .filter(NewsArticle.url == row["url"])
                .first()
            )
            if exists:
                continue
            art = repo.create(
                title=row["title"],
                content=row["content"],
                url=row["url"],
                source=row["source"],
                published_at=datetime.now(timezone.utc),
                category=row["category"],
                language=row["language"],
            )
            aph_repo.create(
                news_article_id=art.id,
                aphorism_text=(
                    "When headlines roar, wisdom whispers: measure twice, "
                    "hope once, act with care."
                ),
                language="en",
                generation_method="summary",
            )
            q = db.query(Quote).filter(Quote.language == "en").first()
            if q:
                pair_repo.create(
                    quote_id=q.id,
                    news_article_id=art.id,
                    relevance_score=72,
                    match_reason="Demo pairing for UI layout.",
                )
        print("Seed complete (skipped existing URLs).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
