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
    # Default uses localhost for non-Docker deployment
    # Set COORDINATOR_URL env var for Docker (e.g., ws://coordinator:20408/ws)
    coordinator_url: str = "ws://localhost:20408/ws"
    coordinator_realm: str = "realm1"
    coordinator_timeout: int = 30
    labgrid_command_timeout: int = 30  # Command execution timeout in seconds
    labgrid_poll_interval_seconds: int = 5

    # CORS settings - accepts comma-separated string or list
    # Use Union[str, List[str]] to prevent pydantic from JSON-parsing strings
    cors_origins: Union[str, List[str]] = ["http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str], None]) -> List[str]:
        """Parse CORS origins from comma-separated string or handle empty values."""
        # Handle None or empty string by returning default
        if v is None or v == "":
            return ["http://localhost:3000"]
        # Parse comma-separated string
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        # Return list as-is
        return v

    # Commands configuration
    commands_file: str = "commands.yaml"

    # Presets configuration (target-to-preset assignments)
    presets_file: str = "target_presets.json"

    # Application settings
    app_name: str = "Labgrid Dashboard API"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


# Labgrid Dashboard user identifier for acquire/release operations
LABGRID_DASHBOARD_USER = "labgrid-dashboard"
