"""
Persistence helpers for news articles.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from models import AphorismNewsPair, NewsArticle, Quote


class NewsRepository:
    """CRUD and listing for news articles."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        title: str,
        content: str,
        url: str,
        source: str = "manual",
        published_at=None,
        category: Optional[str] = None,
        language: str = "en",
    ) -> NewsArticle:
        article = NewsArticle(
            title=title,
            content=content,
            url=url,
            source=source,
            published_at=published_at,
            category=category,
            language=language,
        )
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)
        return article

    def get_by_id(self, article_id: int) -> Optional[NewsArticle]:
        return self.db.get(NewsArticle, article_id)

    def get_detail(self, article_id: int) -> Optional[NewsArticle]:
        return (
            self.db.query(NewsArticle)
            .options(
                joinedload(NewsArticle.aphorisms),
                joinedload(NewsArticle.pairs)
                .joinedload(AphorismNewsPair.quote)
                .joinedload(Quote.author),
                joinedload(NewsArticle.pairs)
                .joinedload(AphorismNewsPair.quote)
                .joinedload(Quote.source),
            )
            .filter(NewsArticle.id == article_id)
            .first()
        )

    def _filtered_query(self, category, search, language):
        q = self.db.query(NewsArticle)
        if category:
            q = q.filter(NewsArticle.category == category)
        if language:
            q = q.filter(NewsArticle.language == language)
        if search and search.strip():
            term = f"%{search.strip()}%"
            q = q.filter(
                or_(
                    NewsArticle.title.ilike(term),
                    NewsArticle.content.ilike(term),
                )
            )
        return q

    def list_articles(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        category: Optional[str] = None,
        search: Optional[str] = None,
        language: Optional[str] = None,
        preload: bool = False,
    ) -> Tuple[List[NewsArticle], int]:
        base = self._filtered_query(category, search, language)
        total = base.count()
        q = self._filtered_query(category, search, language)
        if preload:
            q = q.options(
                joinedload(NewsArticle.aphorisms),
                joinedload(NewsArticle.pairs)
                .joinedload(AphorismNewsPair.quote)
                .joinedload(Quote.author),
                joinedload(NewsArticle.pairs)
                .joinedload(AphorismNewsPair.quote)
                .joinedload(Quote.source),
            )
        rows = (
            q.order_by(
                NewsArticle.published_at.desc().nullslast(),
                NewsArticle.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return rows, total

    def mark_processed(self, article_id: int) -> None:
        art = self.get_by_id(article_id)
        if not art:
            return
        art.processed_at = datetime.utcnow()
        self.db.add(art)
        self.db.commit()
