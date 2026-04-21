"""
Persistence for quote ↔ news pairings.
"""

from typing import List

from sqlalchemy.orm import Session

from models import AphorismNewsPair


class AphorismNewsPairRepository:
    """CRUD for aphorism_news_pairs."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def delete_for_article(self, news_article_id: int) -> None:
        self.db.query(AphorismNewsPair).filter(
            AphorismNewsPair.news_article_id == news_article_id
        ).delete()
        self.db.commit()

    def create(
        self,
        *,
        quote_id: int,
        news_article_id: int,
        relevance_score: int,
        match_reason: str,
    ) -> AphorismNewsPair:
        row = AphorismNewsPair(
            quote_id=quote_id,
            news_article_id=news_article_id,
            relevance_score=relevance_score,
            match_reason=match_reason,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_for_article(self, news_article_id: int) -> List[AphorismNewsPair]:
        return (
            self.db.query(AphorismNewsPair)
            .filter(AphorismNewsPair.news_article_id == news_article_id)
            .order_by(AphorismNewsPair.relevance_score.desc())
            .all()
        )
