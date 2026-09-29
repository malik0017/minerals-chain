"""
app/core/csrf_middleware.py
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_FORM_FIELD, EXEMPT_PATHS, generate_csrf_token

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        is_new_token = cookie_token is None
        effective_token = cookie_token or generate_csrf_token()
        request.state.csrf_token = effective_token

        if request.method in _UNSAFE_METHODS and request.url.path not in EXEMPT_PATHS:
            content_type = request.headers.get("content-type", "")
            submitted_token = None
            if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
                await request.body()
                form = await request.form()
                submitted_token = form.get(CSRF_FORM_FIELD)

            if not cookie_token or not submitted_token or submitted_token != cookie_token:
                from app.core.templates import templates

                return templates.TemplateResponse(
                    request, "errors/csrf_failed.html", {"lang": "en"}, status_code=400
                )

        response = await call_next(request)

        if is_new_token:
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=effective_token,
                httponly=True, 
                samesite="lax",
                secure=settings.cookie_secure_effective,
                max_age=60 * 60 * 24 * 30,  # 30 days — a long-lived anti-CSRF token, not a session credential
            )

        return response
