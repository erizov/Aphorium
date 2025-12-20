"""
End-to-end tests for data ingestion workflow.
"""

import pytest
from sqlalchemy.orm import Session

from repositories.author_repository import AuthorRepository
from repositories.source_repository import SourceRepository
from repositories.quote_repository import QuoteRepository
from scrapers.ingest import ingest_author
from tests.conftest import db_session


def test_ingest_author_creates_data(db_session: Session):
    """
    Test that ingesting an author creates author, sources, and quotes.

    Note: This test requires network access and may be slow.
    Mark with @pytest.mark.skip to skip in CI.
    """
    pytest.skip("Requires network access - run manually")

    # This would test actual WikiQuote scraping
    # For now, we'll test the repository layer instead
    author_repo = AuthorRepository(db_session)
    source_repo = SourceRepository(db_session)
    quote_repo = QuoteRepository(db_session)

    # Create author
    author = author_repo.create(
        name="William Shakespeare",
        language="en",
        bio="English playwright"
    )

    # Create source
    source = source_repo.create(
        title="Hamlet",
        language="en",
        author_id=author.id,
        source_type="play"
    )

    # Create quotes
    quote1 = quote_repo.create(
        text="To be or not to be, that is the question.",
        author_id=author.id,
        source_id=source.id,
        language="en"
    )

    quote2 = quote_repo.create(
        text="Something is rotten in the state of Denmark.",
        author_id=author.id,
        source_id=source.id,
        language="en"
    )

    # Verify data was created
    assert author.id is not None
    assert source.id is not None
    assert quote1.id is not None
    assert quote2.id is not None

    # Verify relationships
    assert quote1.author_id == author.id
    assert quote1.source_id == source.id
    assert quote2.author_id == author.id
    assert quote2.source_id == source.id


def test_ingestion_workflow(db_session: Session):
    """Test complete ingestion workflow with mock data."""
    author_repo = AuthorRepository(db_session)
    source_repo = SourceRepository(db_session)
    quote_repo = QuoteRepository(db_session)

    # Simulate ingestion workflow
    author = author_repo.get_or_create(
        name="Test Author",
        language="en",
        bio="Test bio"
    )

    source = source_repo.get_or_create(
        title="Test Book",
        language="en",
        author_id=author.id
    )

    quotes = [
        "First test quote.",
        "Second test quote.",
        "Third test quote."
    ]

    created_quotes = []
    for quote_text in quotes:
        quote = quote_repo.create(
            text=quote_text,
            author_id=author.id,
            source_id=source.id,
            language="en"
        )
        created_quotes.append(quote)

    # Verify
    assert len(created_quotes) == 3
    assert all(q.author_id == author.id for q in created_quotes)
    assert all(q.source_id == source.id for q in created_quotes)

