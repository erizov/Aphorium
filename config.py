"""
Configuration management for Aphorium.

Loads settings from environment variables with sensible defaults.
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/aphorium"
    )

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: Optional[str] = os.getenv("LOG_FILE", "logs/aphorium.log")

    # API
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))

    # Scraping
    wikiquote_ru_base_url: str = os.getenv(
        "WIKIQUOTE_RU_BASE_URL",
        "https://ru.wikiquote.org"
    )
    wikiquote_en_base_url: str = os.getenv(
        "WIKIQUOTE_EN_BASE_URL",
        "https://en.wikiquote.org"
    )
    scrape_delay: float = float(os.getenv("SCRAPE_DELAY", "1.0"))

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()

