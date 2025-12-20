"""
Database models for Aphorium.

Defines SQLAlchemy models for authors, sources, quotes, and translations.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, TIMESTAMP, Index,
    UniqueConstraint, TypeDecorator
)
from sqlalchemy.orm import relationship

# Import TSVECTOR for PostgreSQL, use Text for SQLite
try:
    from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
    HAS_POSTGRES_TYPES = True
except ImportError:
    HAS_POSTGRES_TYPES = False
    PG_TSVECTOR = None

from database import Base


# Type that works for both PostgreSQL and SQLite
class SearchVectorType(TypeDecorator):
    """Search vector type that adapts to database dialect."""
    
    impl = Text
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql' and HAS_POSTGRES_TYPES:
            return dialect.type_descriptor(PG_TSVECTOR())
        else:
            return dialect.type_descriptor(Text())


class Author(Base):
    """Author model."""

    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    language = Column(String(10), nullable=False)  # 'en' or 'ru'
    bio = Column(Text, nullable=True)
    wikiquote_url = Column(String(500), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    quotes = relationship("Quote", back_populates="author")
    sources = relationship("Source", back_populates="author")

    def __repr__(self) -> str:
        return f"<Author(id={self.id}, name='{self.name}', " \
               f"language='{self.language}')>"


class Source(Base):
    """Literary source model (book, play, poem, etc.)."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=True)
    source_type = Column(String(50), nullable=True)  # 'book', 'play', etc.
    language = Column(String(10), nullable=False)
    wikiquote_url = Column(String(500), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    author = relationship("Author", back_populates="sources")
    quotes = relationship("Quote", back_populates="source")

    def __repr__(self) -> str:
        return f"<Source(id={self.id}, title='{self.title}', " \
               f"language='{self.language}')>"


class Quote(Base):
    """Quote model."""

    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    language = Column(String(10), nullable=False)
    search_vector = Column(SearchVectorType(), nullable=True)  # Full-text search
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    author = relationship("Author", back_populates="quotes")
    source = relationship("Source", back_populates="quotes")
    translations = relationship(
        "QuoteTranslation",
        foreign_keys="QuoteTranslation.quote_id",
        back_populates="quote"
    )
    translated_by = relationship(
        "QuoteTranslation",
        foreign_keys="QuoteTranslation.translated_quote_id",
        back_populates="translated_quote"
    )

    # Indexes
    __table_args__ = (
        Index("idx_quotes_language", "language"),
        Index("idx_quotes_author", "author_id"),
    )

    def __repr__(self) -> str:
        text_preview = self.text[:50] + "..." if len(self.text) > 50 \
            else self.text
        return f"<Quote(id={self.id}, text='{text_preview}', " \
               f"language='{self.language}')>"


class QuoteTranslation(Base):
    """Translation relationship between quotes."""

    __tablename__ = "quote_translations"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    translated_quote_id = Column(
        Integer, ForeignKey("quotes.id"), nullable=False
    )
    confidence = Column(Integer, default=0)  # 0-100
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    quote = relationship(
        "Quote",
        foreign_keys=[quote_id],
        back_populates="translations"
    )
    translated_quote = relationship(
        "Quote",
        foreign_keys=[translated_quote_id],
        back_populates="translated_by"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("quote_id", "translated_quote_id"),
    )

    def __repr__(self) -> str:
        return f"<QuoteTranslation(quote_id={self.quote_id}, " \
               f"translated_quote_id={self.translated_quote_id}, " \
               f"confidence={self.confidence})>"


class SourceMetadata(Base):
    """Metadata for scraped sources."""

    __tablename__ = "sources_metadata"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(50), nullable=False)  # 'wikiquote_ru', etc.
    page_url = Column(String(500), nullable=False)
    last_scraped = Column(TIMESTAMP, nullable=True)
    status = Column(String(50), nullable=True)  # 'pending', 'completed', etc.

    # Constraints
    __table_args__ = (
        UniqueConstraint("source_type", "page_url"),
    )

    def __repr__(self) -> str:
        return f"<SourceMetadata(source_type='{self.source_type}', " \
               f"page_url='{self.page_url}', status='{self.status}')>"

