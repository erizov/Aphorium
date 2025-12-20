"""
Pytest configuration and fixtures.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from models import Quote, Author, Source
from config import settings


# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_session():
    """
    Create a test database session.

    Yields:
        Database session
    """
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_author(db_session):
    """Create a sample author for testing."""
    author = Author(
        name="Test Author",
        language="en",
        bio="Test biography"
    )
    db_session.add(author)
    db_session.commit()
    db_session.refresh(author)
    return author


@pytest.fixture
def sample_source(db_session, sample_author):
    """Create a sample source for testing."""
    source = Source(
        title="Test Book",
        language="en",
        author_id=sample_author.id,
        source_type="book"
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture
def sample_quote(db_session, sample_author, sample_source):
    """Create a sample quote for testing."""
    quote = Quote(
        text="This is a test quote.",
        language="en",
        author_id=sample_author.id,
        source_id=sample_source.id
    )
    db_session.add(quote)
    db_session.commit()
    db_session.refresh(quote)
    return quote

