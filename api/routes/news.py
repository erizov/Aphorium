"""
News ingestion, LLM aphorisms, pairings, and WebSocket notifications.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from api.models.schemas import (
    CreateNewsArticleSchema,
    NewsApiIngestSchema,
    NewsArticleDetailSchema,
    NewsArticleListItemSchema,
    NewsAphorismBriefSchema,
    PaginatedNewsArticlesSchema,
    ProminentNewsIngestSchema,
    RelatedQuoteBriefSchema,
    RssIngestSchema,
    SummarizeArticleSchema,
    NewsAuthorBriefSchema,
    NewsQuoteNestedSchema,
    NewsSourceBriefSchema,
)
from config import settings
from database import get_db
from models import AphorismNewsPair, NewsArticle, NewsAphorism
from repositories.news_repository import NewsRepository
from services.ai_aphorism_service import AIAphorismService
from services.news_ingestion_service import NewsIngestionService
from services.news_processor import process_news_article
from services.notification_service import news_ws_manager
from logger_config import logger

router = APIRouter()

LIST_APHORISM_CAP = 3
LIST_PAIR_CAP = 3


def _author_brief(author: Any) -> Optional[NewsAuthorBriefSchema]:
    if author is None:
        return None
    return NewsAuthorBriefSchema(
        id=author.id,
        name_en=author.name_en,
        name_ru=author.name_ru,
    )


def _source_brief(source: Any) -> Optional[NewsSourceBriefSchema]:
    if source is None:
        return None
    return NewsSourceBriefSchema(
        id=source.id,
        title=source.title,
        language=source.language,
    )


def _quote_nested(quote: Any) -> NewsQuoteNestedSchema:
    return NewsQuoteNestedSchema(
        id=quote.id,
        text=quote.text,
        language=quote.language,
        author=_author_brief(quote.author),
        source=_source_brief(quote.source),
    )


def _serialize_article_list(
    article: NewsArticle,
    *,
    aphorism_cap: int = LIST_APHORISM_CAP,
    pair_cap: int = LIST_PAIR_CAP,
    content_preview_len: int = 240,
) -> NewsArticleListItemSchema:
    aphs = sorted(
        article.aphorisms,
        key=lambda a: a.created_at or a.id,
        reverse=True,
    )[:aphorism_cap]
    pairs = sorted(
        article.pairs,
        key=lambda p: p.relevance_score,
        reverse=True,
    )[:pair_cap]
    preview = (
        article.content[:content_preview_len]
        if article.content
        else None
    )
    return NewsArticleListItemSchema(
        id=article.id,
        title=article.title,
        url=article.url,
        source=article.source,
        published_at=article.published_at,
        category=article.category,
        language=article.language,
        content_preview=preview,
        aphorisms=[
            NewsAphorismBriefSchema(
                id=a.id,
                aphorism_text=a.aphorism_text,
                generation_method=a.generation_method,
                language=a.language,
            )
            for a in aphs
        ],
        related_quotes=[
            RelatedQuoteBriefSchema(
                relevance_score=p.relevance_score,
                match_reason=p.match_reason,
                quote=_quote_nested(p.quote),
            )
            for p in pairs
            if p.quote is not None
        ],
    )


def _serialize_article_detail(article: NewsArticle) -> NewsArticleDetailSchema:
    aphs = sorted(
        article.aphorisms,
        key=lambda a: a.created_at or a.id,
        reverse=True,
    )
    pairs = sorted(
        article.pairs,
        key=lambda p: p.relevance_score,
        reverse=True,
    )
    preview = (
        article.content[:240]
        if article.content
        else None
    )
    return NewsArticleDetailSchema(
        id=article.id,
        title=article.title,
        url=article.url,
        source=article.source,
        published_at=article.published_at,
        category=article.category,
        language=article.language,
        content_preview=preview,
        content=article.content,
        aphorisms=[
            NewsAphorismBriefSchema(
                id=a.id,
                aphorism_text=a.aphorism_text,
                generation_method=a.generation_method,
                language=a.language,
            )
            for a in aphs
        ],
        related_quotes=[
            RelatedQuoteBriefSchema(
                relevance_score=p.relevance_score,
                match_reason=p.match_reason,
                quote=_quote_nested(p.quote),
            )
            for p in pairs
            if p.quote is not None
        ],
    )


@router.get("/articles", response_model=PaginatedNewsArticlesSchema)
def list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    q: Optional[str] = None,
    language: Optional[str] = None,
    db: Session = Depends(get_db),
) -> PaginatedNewsArticlesSchema:
    skip = (page - 1) * page_size
    rows, total = NewsRepository(db).list_articles(
        skip=skip,
        limit=page_size,
        category=category,
        search=q,
        language=language,
        preload=True,
    )
    items = [_serialize_article_list(r) for r in rows]
    return PaginatedNewsArticlesSchema(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/articles/{article_id}", response_model=NewsArticleDetailSchema)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
) -> NewsArticleDetailSchema:
    art = NewsRepository(db).get_detail(article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    return _serialize_article_detail(art)


@router.post("/articles", response_model=NewsArticleDetailSchema)
def create_article(
    body: CreateNewsArticleSchema,
    db: Session = Depends(get_db),
) -> NewsArticleDetailSchema:
    svc = NewsIngestionService(db)
    art = svc.ingest_article(body.model_dump())
    art = NewsRepository(db).get_detail(art.id)
    if not art:
        raise HTTPException(status_code=500, detail="Failed to load article")
    return _serialize_article_detail(art)


@router.post("/articles/{article_id}/process")
async def run_process_pipeline(
    article_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        art = process_news_article(db, article_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Article not found")
    except Exception as exc:
        logger.exception("process pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if settings.websocket_enabled:
        try:
            await news_ws_manager.broadcast(
                {
                    "type": "news_processed",
                    "article_id": article_id,
                    "title": art.title,
                }
            )
        except Exception as exc:
            logger.debug("WS broadcast skipped: %s", exc)
    return {"ok": True, "article_id": article_id}


@router.get("/breaking", response_model=PaginatedNewsArticlesSchema)
def list_breaking(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedNewsArticlesSchema:
    return list_articles(
        page=page,
        page_size=page_size,
        category="breaking",
        q=None,
        language=None,
        db=db,
    )


@router.post("/summarize")
def summarize_article(
    body: SummarizeArticleSchema,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    if body.article_id is not None:
        art = NewsRepository(db).get_by_id(body.article_id)
    else:
        svc = NewsIngestionService(db)
        try:
            art = svc.get_or_ingest_article_by_url(body.url or "")
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    ai = AIAphorismService(db)
    try:
        text = ai.generate_aphoristic_summary(art)
    except Exception as exc:
        logger.warning("Summarize failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="LLM unavailable",
        ) from exc
    return {"aphorism_text": text}


@router.post("/ingest-rss")
def ingest_rss(body: RssIngestSchema, db: Session = Depends(get_db)) -> Dict[str, int]:
    svc = NewsIngestionService(db)
    inserted = svc.ingest_rss_feed(body.feed_url.strip())
    return {"inserted": inserted}


@router.post("/ingest-newsapi")
def ingest_newsapi(
    body: NewsApiIngestSchema,
    db: Session = Depends(get_db),
) -> Dict[str, int]:
    if not settings.news_api_key:
        raise HTTPException(
            status_code=400,
            detail="news_api_key is not configured",
        )
    svc = NewsIngestionService(db)
    inserted = svc.ingest_from_newsapi(
        body.category,
        language=body.language,
        country=body.country,
        page_size=body.page_size,
    )
    return {"inserted": inserted}


@router.post("/ingest-prominent")
def ingest_prominent_news(
    body: ProminentNewsIngestSchema,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    svc = NewsIngestionService(db)
    countries = [c.strip().lower() for c in body.countries if c.strip()]
    invalid = sorted(set(c for c in countries if c not in {"ru", "us"}))
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported countries: {', '.join(invalid)}",
        )
    return svc.ingest_prominent_recent_news(
        days=body.days,
        limit_per_category=body.limit_per_category,
        countries=countries or ["ru", "us"],
    )


@router.get("/pairs")
def search_pairs(
    q: str = Query("", max_length=300),
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    base = db.query(AphorismNewsPair).join(NewsArticle)
    if q.strip():
        term = f"%{q.strip()}%"
        base = base.filter(
            NewsArticle.title.ilike(term)
            | AphorismNewsPair.match_reason.ilike(term)
        )
    rows = (
        base.order_by(AphorismNewsPair.created_at.desc())
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for p in rows:
        art = p.article
        out.append(
            {
                "pair_id": p.id,
                "relevance_score": p.relevance_score,
                "match_reason": p.match_reason,
                "article": {
                    "id": art.id,
                    "title": art.title,
                    "url": art.url,
                },
                "quote": _quote_nested(p.quote).model_dump(),
            }
        )
    return out


@router.get("/{article_id}/aphorisms", response_model=List[NewsAphorismBriefSchema])
def list_aphorisms_for_article(
    article_id: int,
    db: Session = Depends(get_db),
) -> List[NewsAphorismBriefSchema]:
    rows = (
        db.query(NewsAphorism)
        .filter(NewsAphorism.news_article_id == article_id)
        .order_by(NewsAphorism.created_at.desc())
        .all()
    )
    return [
        NewsAphorismBriefSchema(
            id=r.id,
            aphorism_text=r.aphorism_text,
            generation_method=r.generation_method,
            language=r.language,
        )
        for r in rows
    ]


@router.get(
    "/{article_id}/related-quotes",
    response_model=List[RelatedQuoteBriefSchema],
)
def list_related_for_article(
    article_id: int,
    db: Session = Depends(get_db),
) -> List[RelatedQuoteBriefSchema]:
    art = NewsRepository(db).get_detail(article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    pairs = sorted(art.pairs, key=lambda p: p.relevance_score, reverse=True)
    return [
        RelatedQuoteBriefSchema(
            relevance_score=p.relevance_score,
            match_reason=p.match_reason,
            quote=_quote_nested(p.quote),
        )
        for p in pairs
        if p.quote is not None
    ]


@router.websocket("/notifications")
async def news_notifications(websocket: WebSocket) -> None:
    if not settings.websocket_enabled:
        await websocket.close(code=4000)
        return
    await news_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        news_ws_manager.disconnect(websocket)
    except Exception:
        news_ws_manager.disconnect(websocket)
