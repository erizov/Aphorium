"""
Pydantic schemas for API request/response models.
"""

from typing import Optional
from pydantic import BaseModel


class AuthorSchema(BaseModel):
    """Author schema."""

    id: int
    name: str
    language: str
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

    id: int
    text: str
    language: str
    author: Optional[AuthorSchema] = None
    source: Optional[SourceSchema] = None
    has_translation: Optional[bool] = None
    translation_count: Optional[int] = None

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

    english: QuoteSchema
    russian: QuoteSchema

