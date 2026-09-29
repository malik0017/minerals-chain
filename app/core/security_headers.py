"""
app/core/security_headers.py
"""
import threading
from collections import Counter

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

CSP_SOURCES = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'"],
    "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    "font-src": ["'self'", "https://fonts.gstatic.com", "data:"],
    "img-src": ["'self'", "data:", "blob:", "https://flagcdn.com", "https://ibaslogic.github.io"],
    "connect-src": ["'self'"],
    "worker-src": ["'self'"],
    "manifest-src": ["'self'"],
    "frame-src": ["'none'"],
    "frame-ancestors": ["'none'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
}
SKIP_CSP = ("/docs", "/redoc", "/openapi.json")

_lock = threading.Lock()
csp_violations: Counter = Counter()


def csp_policy() -> str:
    parts = [f"{k} {' '.join(v)}" for k, v in CSP_SOURCES.items()]
    if settings.cookie_secure_effective:
        parts.append("upgrade-insecure-requests")
    parts.append("report-uri /csp-report")
    return "; ".join(parts)


def csp_header_name() -> str | None:
    mode = (settings.CSP_MODE or "").lower()
    if mode == "enforce":
        return "Content-Security-Policy"
    if mode == "off":
        return None
    return "Content-Security-Policy-Report-Only"


def record_violation(report: dict) -> None:
    body = report.get("csp-report", report) if isinstance(report, dict) else {}
    key = f"{body.get('effective-directive') or body.get('violated-directive', '?')} ← {body.get('blocked-uri', '?')}"
    with _lock:
        csp_violations[key[:200]] += 1


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if settings.cookie_secure_effective:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        name = csp_header_name()
        if name and "text/html" in h.get("content-type", "") and not request.url.path.startswith(SKIP_CSP):
            h.setdefault(name, csp_policy())
        if request.cookies.get("mc_session") and not request.url.path.startswith(("/static", "/assets")):
            h.setdefault("Cache-Control", "no-store")
        return response


def checklist_item() -> dict:
    mode = (settings.CSP_MODE or "report-only").lower()
    total = sum(csp_violations.values())
    level = "ok" if mode == "enforce" else ("info" if mode != "off" else "warn")
    detail = {"enforce": "Enforced", "off": "Disabled"}.get(mode, "Report-only") + f" · {total} violation report(s) since start."
    return {"key": "csp", "level": level, "title": "Content-Security-Policy", "detail": detail,
            "fix": "Review violation reports, then set CSP_MODE=enforce.", "kind": "env" if level != "ok" else "none",
            "env": {} if level == "ok" else {"CSP_MODE": "enforce"}, "toggle": None, "link": None}
