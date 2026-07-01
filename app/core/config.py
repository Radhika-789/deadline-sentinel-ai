"""
Centralized application configuration.

Uses pydantic-settings to load and validate environment variables
in one place, so no other module ever calls os.getenv() directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings, loaded from environment variables."""

    gemini_api_key: str
    database_url: str = "sqlite:///./deadline_sentinel.db"
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Single shared instance — import this everywhere instead of
# instantiating Settings() again, so config is loaded only once.
settings = Settings()