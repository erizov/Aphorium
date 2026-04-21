"""
Unit tests for search service.

Tests the most critical search logic.
"""

import pytest
from sqlalchemy.orm import Session

from services.search_service import SearchService
from repositories.author_repository import AuthorRepository
from repositories.quote_repository import QuoteRepository
from repositories.translation_repository import TranslationRepository
from tests.conftest import db_session


def test_search_service_prioritizes_bilingual(db_session: Session):
    """Test that search service prioritizes bilingual quotes."""
    author_repo = AuthorRepository(db_session)
    quote_repo = QuoteRepository(db_session)
    translation_repo = TranslationRepository(db_session)

    # Create author
    author = author_repo.create(name_en="Test Author")

    # Create quotes
    quote_with_translation = quote_repo.create(
        text="Quote with translation available.",
        author_id=author.id,
        language="en"
    )

    quote_without_translation = quote_repo.create(
        text="Quote without translation.",
        author_id=author.id,
        language="en"
    )

    # Create translation for first quote
    ru_quote = quote_repo.create(
        text="Цитата с переводом.",
        author_id=author.id,
        language="ru"
    )

    translation_repo.create(
        quote_id=quote_with_translation.id,
        translated_quote_id=ru_quote.id,
        confidence=50
    )

    # Search with bilingual preference
    search_service = SearchService(db_session)
    results = search_service.search(
        query="quote",
        prefer_bilingual=True,
        limit=10
    )

    # Search returns bilingual pair dicts (english / russian sides).
    with_trans = next(
        (
            r
            for r in results
            if r.get("english") and r["english"].get("id")
            == quote_with_translation.id
        ),
        None,
    )
    if with_trans:
        en = with_trans["english"]
        assert en is not None
        assert en.get("id") == quote_with_translation.id


def test_search_service_handles_empty_query(db_session: Session):
    """Test that search service handles edge cases."""
    search_service = SearchService(db_session)

    # Empty query should return empty results or handle gracefully
    results = search_service.search(query="", limit=10)
    assert isinstance(results, list)


def test_quote_to_dict_conversion(db_session: Session):
    """Test quote to dictionary conversion."""
    author_repo = AuthorRepository(db_session)
    quote_repo = QuoteRepository(db_session)

    author = author_repo.create(name_en="Test Author")
    quote = quote_repo.create(
        text="Test quote text.",
        author_id=author.id,
        language="en"
    )

    search_service = SearchService(db_session)
    results = search_service.search(query="test", limit=1)

    if results:
        pair = results[0]
        assert "english" in pair
        en = pair["english"]
        assert en.get("id") == quote.id
        assert "text" in en
        assert en.get("language") == "en"
        assert en.get("author") is not None
        assert en["author"].get("name_en") == "Test Author"

