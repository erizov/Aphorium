"""
Run LLM pipeline on a stored news article (aphorisms + pairings).
"""

from typing import Optional

from sqlalchemy.orm import Session

from models import AphorismNewsPair, NewsAphorism, NewsArticle, NewsNotification
from repositories.aphorism_news_pair_repository import (
    AphorismNewsPairRepository,
)
from repositories.news_aphorism_repository import NewsAphorismRepository
from repositories.news_repository import NewsRepository
from services.ai_aphorism_service import AIAphorismService
from logger_config import logger


def process_news_article(
    db: Session,
    article_id: int,
    *,
    broadcast: Optional[dict] = None,
) -> NewsArticle:
    """
    Regenerate aphorisms and quote pairings for one article.

    Args:
        db: DB session.
        article_id: Target news row.
        broadcast: Reserved for future out-of-band notifications.

    Returns:
        Refreshed NewsArticle ORM instance.
    """
    _ = broadcast
    news_repo = NewsRepository(db)
    article = news_repo.get_by_id(article_id)
    if not article:
        raise ValueError(f"news article {article_id} not found")

    aph_id_rows = [
        row[0]
        for row in db.query(NewsAphorism.id)
        .filter(NewsAphorism.news_article_id == article_id)
        .all()
    ]
    if aph_id_rows:
        db.query(NewsNotification).filter(
            NewsNotification.news_aphorism_id.in_(aph_id_rows)
        ).delete(synchronize_session=False)
    db.query(NewsAphorism).filter(
        NewsAphorism.news_article_id == article_id
    ).delete(synchronize_session=False)
    db.query(AphorismNewsPair).filter(
        AphorismNewsPair.news_article_id == article_id
    ).delete(synchronize_session=False)
    db.commit()

    ai = AIAphorismService(db)
    aph_repo = NewsAphorismRepository(db)
    pair_repo = AphorismNewsPairRepository(db)

    try:
        summary_text = ai.generate_aphoristic_summary(article)
    except Exception as exc:
        logger.warning("Summary aphorism failed: %s", exc)
        summary_text = (
            "Generated aphorism unavailable: configure OPENAI_API_KEY, set "
            "LLM_PROVIDER=local with a running Ollama/model, then reprocess. "
            "(Archive quote matching runs separately and may still appear.)"
        )
    aph_repo.create(
        news_article_id=article.id,
        aphorism_text=summary_text,
        language=article.language,
        generation_method="summary",
    )

    if article.category == "breaking":
        try:
            alert_text = ai.transform_to_aphorism(
                article.content,
                language=article.language,
                context={"title": article.title},
            )
            aph_repo.create(
                news_article_id=article.id,
                aphorism_text=alert_text,
                language=article.language,
                generation_method="breaking_alert",
            )
        except Exception as exc:
            logger.warning("Breaking aphorism failed: %s", exc)

    try:
        matches = ai.find_relevant_aphorisms(article, limit=5)
    except Exception as exc:
        logger.warning("Pairing failed: %s", exc)
        matches = []

    seen = set()
    for row in matches:
        qid = int(row["quote_id"])
        if qid in seen:
            continue
        seen.add(qid)
        try:
            pair_repo.create(
                quote_id=qid,
                news_article_id=article.id,
                relevance_score=max(
                    0, min(100, int(row.get("relevance_score", 50)))
                ),
                match_reason=str(row.get("match_reason", ""))[:2000],
            )
        except Exception as exc:
            logger.debug("Skip duplicate or bad pair %s: %s", qid, exc)

    news_repo.mark_processed(article.id)
    db.refresh(article)
    return article
