"""
Turn news into aphorisms and suggest related quotes using the LLM stack.
"""

import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import NewsArticle, Quote
from repositories.quote_repository import QuoteRepository
from services.llm_client import chat_complete, chat_complete_json
from logger_config import logger


class AIAphorismService:
    """LLM-backed transforms for news content."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.quote_repo = QuoteRepository(db)

    def transform_to_aphorism(
        self,
        news_text: str,
        *,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """One-liner aphorism for breaking-style alerts."""
        ctx = context or {}
        title = ctx.get("title", "")
        prompt = (
            "Transform this breaking news into a memorable one-liner "
            "aphorism that captures both the facts and broader significance. "
            "Make it digestible and less anxiety-inducing. "
            "Reply with the aphorism only, no quotes or labels.\n\n"
            f"Title: {title}\n\nBody:\n{news_text[:4000]}"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    f"You write short aphorisms in {language}. "
                    "Be concise (max 220 characters)."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return chat_complete(messages, max_tokens=200, temperature=0.5)[
            :500
        ]

    def generate_aphoristic_summary(
        self,
        article: NewsArticle,
    ) -> str:
        """Social-style aphoristic summary of a full article."""
        body = article.content[:6000]
        prompt = (
            "Summarize this news article as a concise aphorism suitable "
            "for social sharing. Capture the key point in a memorable, "
            "quotable format. Reply with the aphorism only.\n\n"
            f"Title: {article.title}\n\nBody:\n{body}"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    f"You write in {article.language}. "
                    "Be concise (max 280 characters)."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return chat_complete(messages, max_tokens=220, temperature=0.5)[
            :600
        ]

    def _candidate_quotes(
        self,
        article: NewsArticle,
        *,
        limit: int,
    ) -> List[Quote]:
        """Find quote candidates with relaxed matching before LLM ranking."""
        language = (
            article.language
            if article.language in ("en", "ru")
            else None
        )
        seen: set[int] = set()
        candidates: List[Quote] = []

        text = f"{article.title} {article.content[:500]}"
        raw_terms = re.split(r"\W+", text)
        terms = [w for w in raw_terms if len(w) > 3][:12]
        queries = [
            " ".join(terms[:6]),
            article.title[:120],
            article.category or "",
            " ".join(terms[6:12]),
        ]

        for query in queries:
            if not query.strip():
                continue
            for quote in self.quote_repo.search(
                query=query.strip(),
                language=language,
                limit=limit,
            ):
                if quote.id not in seen:
                    candidates.append(quote)
                    seen.add(quote.id)
                if len(candidates) >= limit:
                    return candidates

        # Last resort: keep the archive populated even when keyword search is
        # too narrow for the story. LLM ranking can still choose among these.
        q = self.db.query(Quote)
        if language:
            q = q.filter(Quote.language == language)
        for quote in q.order_by(Quote.id.desc()).limit(limit).all():
            if quote.id not in seen:
                candidates.append(quote)
                seen.add(quote.id)

        return candidates[:limit]

    def find_relevant_aphorisms(
        self,
        article: NewsArticle,
        *,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return candidate pair dicts: quote_id, relevance_score, match_reason.

        Uses search for candidates, then LLM JSON ranking when possible.
        """
        quotes = self._candidate_quotes(article, limit=40)
        if not quotes:
            return []

        candidates: List[Quote] = quotes[:25]
        lines = []
        for c in candidates:
            lines.append(f"id={c.id}\t{c.text[:220]}")
        catalog = "\n".join(lines)
        user = (
            "News title:\n"
            f"{article.title}\n\n"
            "News excerpt:\n"
            f"{article.content[:800]}\n\n"
            "Candidate aphorisms (tab-separated id and text):\n"
            f"{catalog}\n\n"
            "Pick up to "
            f"{limit} ids that best resonate thematically. "
            "Respond with JSON only: a list of objects "
            '{"quote_id": int, "relevance_score": int, "match_reason": str}'
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You map news to historical short quotes. "
                    "Scores are integers 0-100. JSON array only."
                ),
            },
            {"role": "user", "content": user},
        ]
        try:
            raw = chat_complete_json(
                messages,
                max_tokens=800,
                temperature=0.2,
            )
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("expected JSON list")
            out: List[Dict[str, Any]] = []
            for row in data[:limit]:
                if not isinstance(row, dict):
                    continue
                qid = row.get("quote_id")
                if qid is None:
                    continue
                out.append(
                    {
                        "quote_id": int(qid),
                        "relevance_score": int(
                            row.get("relevance_score", 50)
                        ),
                        "match_reason": str(row.get("match_reason", "")),
                    }
                )
            if out:
                return out
        except Exception as exc:
            logger.warning("LLM pairing failed, using search order: %s", exc)

        fallback: List[Dict[str, Any]] = []
        for c in candidates[:limit]:
            fallback.append(
                {
                    "quote_id": c.id,
                    "relevance_score": 35,
                    "match_reason": (
                        "Relaxed archive match; LLM ranking was unavailable."
                    ),
                }
            )
        return fallback
