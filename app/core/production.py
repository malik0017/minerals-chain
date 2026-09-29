"""
app/core/production.py
"""
import logging
import sys

from app.core.config import Settings

log = logging.getLogger("minerals")


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(getattr(h, "_mc", False) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler._mc = True
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", "%Y-%m-%dT%H:%M:%S%z"))
    root.addHandler(handler)
    root.setLevel(level.upper())
    for noisy in ("sqlalchemy.engine", "passlib", "httpx", "httpcore", "multipart", "alembic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def problems(s: Settings) -> tuple[list[str], list[str]]:
    fatal, warn = [], []
    if s.SECRET_KEY.startswith(("CHANGE_ME", "GENERATE")) or len(s.SECRET_KEY) < 32:
        fatal.append("SECRET_KEY is the default or shorter than 32 characters.")
    if s.DEBUG:
        fatal.append("DEBUG must be false.")
    if not s.FILE_ENCRYPTION_KEY or s.FILE_ENCRYPTION_KEY.startswith("GENERATE"):
        fatal.append("FILE_ENCRYPTION_KEY is not set — uploaded documents would be stored unencrypted.")
    if not s.PUBLIC_BASE_URL.startswith("https://"):
        fatal.append("PUBLIC_BASE_URL must be the https:// address of the site.")
    if s.EMAIL_MODE != "smtp":
        warn.append("EMAIL_MODE is not smtp — OTP and notification emails are only printed to the log.")
    if not s.REDIS_URL:
        warn.append("REDIS_URL is not set — rate limits are per worker process.")
    if s.CSP_MODE != "enforce":
        warn.append("CSP_MODE is not 'enforce'.")
    if s.WATHQ_MODE != "live":
        warn.append(f"WATHQ_MODE is '{s.WATHQ_MODE}' — registry checks are not hitting Wathq.")
    return fatal, warn


def enforce(s: Settings) -> None:
    if s.APP_ENV != "production":
        return
    fatal, warn = problems(s)
    for w in warn:
        log.warning("config: %s", w)
    if fatal:
        raise RuntimeError("Refusing to start in production:\n  - " + "\n  - ".join(fatal))
