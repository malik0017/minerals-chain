
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

    # --- Cookie hardening (Batch G) ---
    # Every cookie this app sets (session, pending-2FA, registration OTP,
    # CSRF, language) is marked `secure` from this ONE flag, so there is
    # nowhere else to remember to flip it on. Left False in local/dev
    # (plain HTTP, e.g. localhost or a Laragon box) because a `secure`
    # cookie is silently DROPPED by the browser over plain HTTP — every
    # login would appear to succeed and then immediately look logged-out.
    # Set COOKIE_SECURE=true in .env once the app is served over HTTPS
    # (staging/production). APP_ENV=production also implies it, so a
    # production deploy is protected even if this specific var is
    # forgotten in .env — the explicit var only needs setting to turn it
    # ON early (e.g. HTTPS in staging) or to force it off in an unusual
    # setup; it can't turn off what APP_ENV=production already requires.
    COOKIE_SECURE: bool = False

    # --- Rate limiting (Batch G) ---
    # In-memory sliding-window limiter (app/core/rate_limit.py) — no new
    # infrastructure dependency, correct for the single-process deployment
    # this app runs as today. Explicitly NOT correct once the app runs
    # behind multiple worker processes/instances (each process would keep
    # its own counters) — swap the store for Redis at that point; the
    # limiter's call sites (login, OTP send/verify) don't need to change,
    # only RateLimiter's internal storage.
    LOGIN_RATE_LIMIT_MAX: int = 10          # attempts per IP
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300     # per 5 minutes
    OTP_SEND_RATE_LIMIT_MAX: int = 3        # sends per email
    OTP_SEND_RATE_LIMIT_WINDOW_SECONDS: int = 900  # per 15 minutes
    OTP_VERIFY_RATE_LIMIT_MAX: int = 5      # verify attempts per pending token
    OTP_VERIFY_RATE_LIMIT_WINDOW_SECONDS: int = 600  # per 10 minutes (matches token lifetime)

    # --- Localization ---
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "ar")

    # --- Email (Batch A) ---
    # EMAIL_MODE="console": nothing is actually sent — every email is
    # printed to the server log instead, so OTP flows (Batch B) and any
    # future transactional email are fully testable with zero SMTP setup.
    # EMAIL_MODE="smtp": sends for real, using the settings below.
    # Switching to production email is a one-line change to this value —
    # nothing in application code needs to change either way, see
    # services/email_service.py.
    EMAIL_MODE: str = "console"        # console | smtp
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "no-reply@mineralschain.com"
    SMTP_FROM_NAME: str = "Minerals Chain"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cookie_secure_effective(self) -> bool:
        """What every set_cookie() call actually uses. True if either the
        explicit COOKIE_SECURE flag is on, or APP_ENV is "production" — so
        a production deploy is covered even if COOKIE_SECURE itself was
        left at its default. See COOKIE_SECURE's docstring above."""
        return self.COOKIE_SECURE or self.APP_ENV == "production"

@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is only parsed once per process."""
    return Settings()


settings = get_settings()
