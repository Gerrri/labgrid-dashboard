"""
Application configuration using pydantic-settings.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Labgrid Coordinator settings
    coordinator_url: str = "ws://coordinator:20408/ws"
    coordinator_realm: str = "realm1"
    coordinator_timeout: int = 30

    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000"]

    # Commands configuration
    commands_file: str = "commands.yaml"

    # Application settings
    app_name: str = "Labgrid Dashboard API"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
