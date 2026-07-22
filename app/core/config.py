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

    # --- Auth / JWT -----------------------------------------------------
    # Required, no default: a shared/default signing key would let
    # anyone forge tokens. Must be set explicitly in .env.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 60 * 24  # 24 hours
    
    admin_email: str
    admin_password: str

    # --- SMTP / Email Settings ------------------------------------------
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@deadlinesentinel.ai"

    # --- Scheduler / Reminder Settings -----------------------------------
    # Made configurable in minutes as requested by the user
    reminder_interval_minutes: int = 60
    reminder_threshold_hours: int = 24

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Single shared instance — import this everywhere instead of
# instantiating Settings() again, so config is loaded only once.
settings = Settings()

gemini_model: str = "gemini-flash-latest"