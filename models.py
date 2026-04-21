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
    name_en = Column(String(255), nullable=True)  # English name version
    name_ru = Column(String(255), nullable=True)  # Russian name version
    bio = Column(Text, nullable=True)
    wikiquote_url = Column(String(500), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    quotes = relationship("Quote", back_populates="author")
    sources = relationship("Source", back_populates="author")

    def __repr__(self) -> str:
        return f"<Author(id={self.id}, name_en='{self.name_en}', " \
               f"name_ru='{self.name_ru}')>"


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
    bilingual_group_id = Column(Integer, nullable=True, index=True)  # Groups EN/RU pairs
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
    aphorism_news_pairs = relationship(
        "AphorismNewsPair",
        back_populates="quote",
    )

    # Indexes
    __table_args__ = (
        Index("idx_quotes_language", "language"),
        Index("idx_quotes_author", "author_id"),
        Index("idx_quotes_bilingual_group", "bilingual_group_id"),
        Index("idx_quotes_group_language", "bilingual_group_id", "language"),
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


class WordTranslation(Base):
    """Translation dictionary for common words."""
    
    __tablename__ = "word_translations"
    
    id = Column(Integer, primary_key=True, index=True)
    word_en = Column(String(255), nullable=False, index=True)
    word_ru = Column(String(255), nullable=False, index=True)
    frequency_en = Column(Integer, default=0)  # Word frequency in English
    frequency_ru = Column(Integer, default=0)  # Word frequency in Russian
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    # Indexes for fast lookup
    __table_args__ = (
        Index('idx_word_en', 'word_en'),
        Index('idx_word_ru', 'word_ru'),
    )
    
    def __repr__(self) -> str:
        return f"<WordTranslation(en='{self.word_en}', ru='{self.word_ru}')>"


class NewsArticle(Base):
    """Ingested news article."""

    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    source = Column(String(100), nullable=False, default="manual")
    published_at = Column(TIMESTAMP, nullable=True)
    category = Column(String(80), nullable=True)
    language = Column(String(10), nullable=False, default="en")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    processed_at = Column(TIMESTAMP, nullable=True)

    aphorisms = relationship(
        "NewsAphorism",
        back_populates="article",
        cascade="all, delete-orphan",
    )
    pairs = relationship(
        "AphorismNewsPair",
        back_populates="article",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_news_articles_published_at", "published_at"),
        Index("idx_news_articles_category", "category"),
    )

    def __repr__(self) -> str:
        t = str(self.title)
        preview = t[:40] + ("..." if len(t) > 40 else "")
        return f"<NewsArticle(id={self.id}, title='{preview}')>"


class NewsAphorism(Base):
    """LLM-generated aphoristic line derived from news."""

    __tablename__ = "news_aphorisms"

    id = Column(Integer, primary_key=True, index=True)
    news_article_id = Column(
        Integer, ForeignKey("news_articles.id"), nullable=False, index=True
    )
    aphorism_text = Column(Text, nullable=False)
    language = Column(String(10), nullable=False, default="en")
    generation_method = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    article = relationship("NewsArticle", back_populates="aphorisms")
    notifications = relationship(
        "NewsNotification",
        back_populates="aphorism",
        cascade="all, delete-orphan",
    )


class AphorismNewsPair(Base):
    """Link between a historical quote and a news article."""

    __tablename__ = "aphorism_news_pairs"

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    news_article_id = Column(
        Integer, ForeignKey("news_articles.id"), nullable=False, index=True
    )
    relevance_score = Column(Integer, nullable=False, default=0)
    match_reason = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    quote = relationship("Quote", back_populates="aphorism_news_pairs")
    article = relationship("NewsArticle", back_populates="pairs")

    __table_args__ = (
        UniqueConstraint("quote_id", "news_article_id"),
        Index("idx_aphorism_news_pairs_article", "news_article_id"),
    )


class NewsNotification(Base):
    """Record of a pushed news aphorism notification."""

    __tablename__ = "news_notifications"

    id = Column(Integer, primary_key=True, index=True)
    news_aphorism_id = Column(
        Integer, ForeignKey("news_aphorisms.id"), nullable=False, index=True
    )
    delivery_method = Column(String(50), nullable=False)
    delivered_at = Column(TIMESTAMP, default=datetime.utcnow)
    recipient_id = Column(String(128), nullable=True)

    aphorism = relationship("NewsAphorism", back_populates="notifications")


