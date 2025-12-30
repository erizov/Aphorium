"""
Pydantic schemas for API request/response models.
"""

from typing import Optional
from pydantic import BaseModel


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

