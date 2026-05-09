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

    def process_article_bundle(
        self,
        article: NewsArticle,
        *,
        related_limit: int = 2,
    ) -> Dict[str, Any]:
        """
        One LLM call: summary aphorism, optional breaking line, quote ranks.

        Used only from ``process_news_article`` (Process button); pairs apply
        to that article only. Not invoked during RSS/NewsAPI ingestion.

        Returns:
            Keys: ``aphorism`` (str), ``breaking_alert`` (optional str),
            ``related_quotes`` (list of dicts with quote_id, relevance_score,
            match_reason). Candidate ids are validated against search results.
        """
        quotes = self._candidate_quotes(article, limit=40)
        candidates: List[Quote] = quotes[:25]
        allowed_ids = {c.id for c in candidates}
        if candidates:
            lines = [f"id={c.id}\t{c.text[:220]}" for c in candidates]
            catalog = "\n".join(lines)
        else:
            catalog = "(no archive candidates in database)"

        cat = (article.category or "").strip().lower()
        is_breaking = cat == "breaking"
        breaking_hint = (
            'Set "breaking_alert" to a second distinct urgent one-liner '
            "(max 220 characters)."
            if is_breaking
            else 'Set "breaking_alert" to null (not breaking news).'
        )
        user = (
            "News title:\n"
            f"{article.title}\n\n"
            "News body excerpt:\n"
            f"{article.content[:800]}\n\n"
            f'News category slug: {article.category or "general"}\n\n'
            "Candidate archive quotes (tab-separated id and text):\n"
            f"{catalog}\n\n"
            "Respond with JSON only — one object with exactly these keys:\n"
            '- "aphorism": string, concise social-style summary (max 280 '
            "characters)\n"
            f'- "breaking_alert": string or null — {breaking_hint}\n'
            '- "related_quotes": array (max '
            f"{related_limit}) of objects, each with "
            '"quote_id" (int from the candidate list), '
            '"relevance_score" (0-100 int), "match_reason" (short string)\n'
            "Use only quote_id values that appear in the candidate list; "
            "if there are no candidates, use an empty array. "
            f"Rank at most {related_limit} quotes for this single news story."
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You produce compact JSON only (no markdown). "
                    f"You write aphorisms in {article.language}. "
                    "When ranking quotes, scores are integers from 0 to 100."
                ),
            },
            {"role": "user", "content": user},
        ]
        raw = chat_complete_json(
            messages,
            max_tokens=1400,
            temperature=0.35,
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM returned invalid JSON: {exc}; snippet: {raw[:240]!r}"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError("LLM JSON must be an object")

        aphorism = data.get("aphorism")
        if not isinstance(aphorism, str) or not aphorism.strip():
            raise ValueError("LLM JSON missing non-empty aphorism string")

        raw_alert = data.get("breaking_alert")
        breaking_alert: Optional[str] = None
        if is_breaking and raw_alert is not None:
            if isinstance(raw_alert, str) and raw_alert.strip():
                breaking_alert = raw_alert.strip()[:500]

        related_raw = data.get("related_quotes")
        if related_raw is None:
            related_raw = []
        if not isinstance(related_raw, list):
            raise ValueError('LLM JSON "related_quotes" must be an array')

        out_rows: List[Dict[str, Any]] = []
        if allowed_ids:
            for row in related_raw[:related_limit * 2]:
                if not isinstance(row, dict):
                    continue
                qid = row.get("quote_id")
                if qid is None:
                    continue
                try:
                    qid_int = int(qid)
                except (TypeError, ValueError):
                    continue
                if qid_int not in allowed_ids:
                    continue
                out_rows.append(
                    {
                        "quote_id": qid_int,
                        "relevance_score": int(
                            row.get("relevance_score", 50)
                        ),
                        "match_reason": str(row.get("match_reason", "")),
                    }
                )
                if len(out_rows) >= related_limit:
                    break

        return {
            "aphorism": aphorism.strip()[:600],
            "breaking_alert": breaking_alert,
            "related_quotes": out_rows,
        }
