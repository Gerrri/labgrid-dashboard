"""
Application configuration using pydantic-settings.
"""

from functools import lru_cache
from typing import List, Union

from pydantic import field_validator
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

    # CORS settings - accepts comma-separated string or list
    cors_origins: List[str] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Commands configuration
    commands_file: str = "commands.yaml"

    # Application settings
    app_name: str = "Labgrid Dashboard API"
    debug: bool = False

    # Mock mode - set to "false" to force real coordinator connection
    # Default: "auto" - automatically falls back to mock if coordinator unavailable
    mock_mode: str = "auto"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
