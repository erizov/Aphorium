"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AuthorSchema(BaseModel):
    """Author schema."""

    id: int
    name: str  # Language-specific name (name_en for EN quotes, name_ru for RU quotes)
    name_en: Optional[str] = None  # English name version
    name_ru: Optional[str] = None  # Russian name version
    bio: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class SourceSchema(BaseModel):
    """Source schema."""

    id: int
    title: str
    language: str
    source_type: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class QuoteSchema(BaseModel):
    """Quote schema."""

    id: Optional[int] = None  # None for translated quotes not in DB
    text: str
    language: str
    author: Optional[AuthorSchema] = None
    source: Optional[SourceSchema] = None
    has_translation: Optional[bool] = None
    translation_count: Optional[int] = None
    created_at: Optional[str] = None  # ISO format timestamp

    class Config:
        """Pydantic config."""

        from_attributes = True


class QuoteWithTranslationsSchema(BaseModel):
    """Quote with translations schema."""

    id: int
    text: str
    language: str
    author: Optional[AuthorSchema] = None
    source: Optional[SourceSchema] = None
    translations: list[QuoteSchema] = []

    class Config:
        """Pydantic config."""

        from_attributes = True


class BilingualPairSchema(BaseModel):
    """Bilingual quote pair schema."""

    english: Optional[QuoteSchema] = None
    russian: Optional[QuoteSchema] = None
    is_translated: bool = False  # True if translation was generated, False if from DB
    translation_source: Optional[str] = None  # e.g., "word_translation_dict" if translated


class NewsAuthorBriefSchema(BaseModel):
    """Minimal author payload for news pairings."""

    id: int
    name_en: Optional[str] = None
    name_ru: Optional[str] = None


class NewsSourceBriefSchema(BaseModel):
    """Minimal source payload for news pairings."""

    id: int
    title: str
    language: str


class NewsQuoteNestedSchema(BaseModel):
    """Quote nested under a news pairing."""

    id: int
    text: str
    language: str
    author: Optional[NewsAuthorBriefSchema] = None
    source: Optional[NewsSourceBriefSchema] = None


class NewsAphorismBriefSchema(BaseModel):
    """Generated aphorism attached to a news row."""

    id: int
    aphorism_text: str
    generation_method: str
    language: str


class RelatedQuoteBriefSchema(BaseModel):
    """Historical quote matched to a news article."""

    relevance_score: int
    match_reason: Optional[str] = None
    quote: NewsQuoteNestedSchema


class NewsArticleListItemSchema(BaseModel):
    """News feed row with nested aphorisms and archive matches."""

    id: int
    title: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    category: Optional[str] = None
    language: str
    content_preview: Optional[str] = None
    aphorisms: List[NewsAphorismBriefSchema] = Field(default_factory=list)
    related_quotes: List[RelatedQuoteBriefSchema] = Field(default_factory=list)


class NewsArticleDetailSchema(NewsArticleListItemSchema):
    """Detail view includes full article body."""

    content: str


class PaginatedNewsArticlesSchema(BaseModel):
    """Paginated news list."""

    items: List[NewsArticleListItemSchema]
    total: int
    page: int
    page_size: int


class CreateNewsArticleSchema(BaseModel):
    """Manual news ingestion."""

    title: str = Field(..., max_length=500)
    content: str
    url: str = Field(..., max_length=1000)
    source: str = "manual"
    category: Optional[str] = Field(None, max_length=80)
    language: str = Field("en", max_length=10)
    published_at: Optional[datetime] = None


class SummarizeArticleSchema(BaseModel):
    """Request body for on-demand summary (exactly one of id or url)."""

    article_id: Optional[int] = Field(None, ge=1)
    url: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def exactly_one_target(self) -> "SummarizeArticleSchema":
        has_id = self.article_id is not None
        has_url = bool(self.url and self.url.strip())
        if has_id == has_url:
            raise ValueError("provide exactly one of article_id or url")
        return self


class RssIngestSchema(BaseModel):
    """Ingest from one RSS feed URL."""

    feed_url: str


class NewsApiIngestSchema(BaseModel):
    """Optional filters for NewsAPI top-headlines ingest."""

    category: Optional[str] = Field(None, max_length=40)
    country: Optional[str] = Field(None, min_length=2, max_length=2)
    language: str = Field("en", max_length=10)
    page_size: int = Field(20, ge=1, le=100)


class ProminentNewsIngestSchema(BaseModel):
    """Ingest recent news from curated RU/US prominent RSS feeds."""

    days: int = Field(30, ge=1, le=30)
    limit_per_category: int = Field(100, ge=1, le=100)
    countries: List[str] = Field(default_factory=lambda: ["ru", "us"])

