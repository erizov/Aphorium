"""
Configuration management for Aphorium.

Loads settings from environment variables with sensible defaults.
Uses Pydantic Settings for validation and type safety.
"""

from typing import List, Optional

from pydantic import Field
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

    # LLM for news aphorism generation / summaries / quote matching.
    # auto: use OpenAI when OPENAI_API_KEY is set, otherwise local.
    # local: use LOCAL_LLM_* only, unless cloud fallback is enabled.
    # openai: require OPENAI_API_KEY and use OpenAI directly.
    llm_provider: str = "auto"
    local_llm_base_url: str = "http://127.0.0.1:11434/v1"
    local_llm_model: str = "llama3.2"
    local_llm_api_key: Optional[str] = "ollama"
    llm_timeout_seconds: float = 120.0
    llm_max_output_tokens: int = 512
    llm_cloud_fallback_enabled: bool = False
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # News ingestion
    news_api_key: Optional[str] = None
    news_api_country: str = "us"
    rss_feeds: List[str] = Field(default_factory=list)
    news_scrape_allowed_hosts: List[str] = Field(default_factory=list)
    breaking_news_keywords: List[str] = Field(
        default_factory=lambda: ["breaking", "alert", "urgent"]
    )
    news_fetch_interval_seconds: int = 300
    news_periodic_fetch_enabled: bool = False
    websocket_enabled: bool = True
    # Archive quotes matched to news via LLM only when user POSTs .../process.
    news_related_quotes_max: int = 2

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


# Create settings instance
settings = Settings()

