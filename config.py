"""
Configuration management for Aphorium.

Loads settings from environment variables with sensible defaults.
Uses Pydantic Settings for validation and type safety.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with validation."""

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/aphorium"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = "logs/aphorium.log"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_port: int = 3000
    
    # CORS
    enable_cors: bool = True
    cors_origins: List[str] = ["*"]

    # Search
    search_limit_max: int = 300
    search_limit_default: int = 50

    # Scraping
    wikiquote_ru_base_url: str = "https://ru.wikiquote.org"
    wikiquote_en_base_url: str = "https://en.wikiquote.org"
    scrape_delay: float = 1.0
    batch_size: int = 100

    # Translation
    translation_provider: str = "google"  # google, deepl, microsoft, mymemory, pons, linguee
    translation_api_key: Optional[str] = None
    translation_delay: float = 0.5

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


# Create settings instance
settings = Settings()

