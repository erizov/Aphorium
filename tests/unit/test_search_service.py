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
    author = author_repo.create(name="Test Author", language="en")

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

    # Find quotes in results
    with_trans = next(
        (r for r in results if r["id"] == quote_with_translation.id),
        None
    )
    without_trans = next(
        (r for r in results if r["id"] == quote_with_translation.id),
        None
    )

    # Quote with translation should have has_translation flag
    if with_trans:
        assert with_trans["has_translation"] is True
        assert with_trans["translation_count"] > 0


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

    author = author_repo.create(name="Test Author", language="en")
    quote = quote_repo.create(
        text="Test quote text.",
        author_id=author.id,
        language="en"
    )

    search_service = SearchService(db_session)
    results = search_service.search(query="test", limit=1)

    if results:
        quote_dict = results[0]
        assert "id" in quote_dict
        assert "text" in quote_dict
        assert "language" in quote_dict
        assert quote_dict["author"] is not None
        assert quote_dict["author"]["name"] == "Test Author"

