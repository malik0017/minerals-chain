"""
app/core/csrf.py
"""
import secrets

CSRF_COOKIE_NAME = "mc_csrf"
CSRF_FORM_FIELD = "csrf_token"

EXEMPT_PATHS: set[str] = {"/csp-report"}
EXEMPT_PREFIXES: tuple[str, ...] = ("/api/v1/",)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
