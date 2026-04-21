"""
Persistence for LLM-generated news aphorisms.
"""

from typing import List

from sqlalchemy.orm import Session

from models import NewsAphorism


class NewsAphorismRepository:
    """CRUD for news_aphorisms rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        news_article_id: int,
        aphorism_text: str,
        language: str,
        generation_method: str,
    ) -> NewsAphorism:
        row = NewsAphorism(
            news_article_id=news_article_id,
            aphorism_text=aphorism_text,
            language=language,
            generation_method=generation_method,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_for_article(self, article_id: int) -> List[NewsAphorism]:
        return (
            self.db.query(NewsAphorism)
            .filter(NewsAphorism.news_article_id == article_id)
            .order_by(NewsAphorism.created_at.desc())
            .all()
        )
