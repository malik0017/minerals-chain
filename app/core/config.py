
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "Minerals Chain"
    APP_ENV: str = "development"       # development | staging | production
    DEBUG: bool = True

    # --- Database ---
    # Example (Laragon/pgAdmin local dev):
    # postgresql://a-m.mudassir:root@localhost:5432/minerals_chain_db
    DATABASE_URL: str

    # --- Security (used from Batch 2 onward, defined now so .env is stable) ---
    SECRET_KEY: str = "CHANGE_ME_DEV_ONLY_NOT_FOR_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h session

    # --- Localization ---
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "ar")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is only parsed once per process."""
    return Settings()


settings = get_settings()
