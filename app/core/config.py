
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
    COOKIE_SECURE: bool = False
    LOGIN_RATE_LIMIT_MAX: int = 10          # attempts per IP
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300     # per 5 minutes
    OTP_SEND_RATE_LIMIT_MAX: int = 3        # sends per email
    OTP_SEND_RATE_LIMIT_WINDOW_SECONDS: int = 900  # per 15 minutes
    OTP_VERIFY_RATE_LIMIT_MAX: int = 5      # verify attempts per pending token
    OTP_VERIFY_RATE_LIMIT_WINDOW_SECONDS: int = 600  # per 10 minutes 

    # --- Localization ---
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "ar")
    EMAIL_MODE: str = "console"        # console | smtp
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "no-reply@mineralschain.com"
    SMTP_FROM_NAME: str = "Minerals Chain"

    REDIS_URL: str = ""
    FILE_ENCRYPTION_KEY: str = ""
    BACKUP_DIR: str = "backups"
    BACKUP_KEEP: int = 14
    PG_BIN_DIR: str = ""
    CSP_MODE: str = "report-only"
    WATHQ_MODE: str = "sandbox"
    WATHQ_API_KEY: str = ""
    WATHQ_BASE_URL: str = "https://api.wathq.sa/v5/commercialregistration"
    WATHQ_TIMEOUT: float = 10.0
    MIM_MODE: str = "sandbox"
    MIM_API_URL: str = ""
    MIM_API_KEY: str = ""
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    FORWARDED_ALLOW_IPS: str = "127.0.0.1,::1,testclient"
    LOG_LEVEL: str = "INFO"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cookie_secure_effective(self) -> bool:
        return self.COOKIE_SECURE or self.APP_ENV == "production"

@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is only parsed once per process."""
    return Settings()


settings = get_settings()
