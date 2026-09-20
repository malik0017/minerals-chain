"""
app/core/csrf_middleware.py

Batch G: the ASGI-level half of the double-submit CSRF scheme described
in core/csrf.py. Registered once in main.py, applies to every request —
no route needs to opt in or remember to check anything itself.

Reads the submitted form for POST/PUT/PATCH/DELETE requests via
Starlette's `await request.form()`. This is the standard,
Starlette-documented way to inspect a request body from middleware:
the parsed FormData is cached on the Request object, so every route
handler downstream (whether it uses FastAPI's `Form(...)` dependency or
calls `request.form()` itself) gets the SAME cached result instead of
trying to re-read an already-consumed stream — this includes multipart
requests with file uploads (avatar upload, registration documents):
the UploadFile objects are cached the same way, nothing is read twice
off the wire.
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_FORM_FIELD, EXEMPT_PATHS, generate_csrf_token

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# NOTE on why this middleware renders its own error response instead of
# raising CSRFValidationException for main.py's @app.exception_handler to
# catch: Starlette builds its middleware stack as
# ServerErrorMiddleware -> [user middleware, this one included] ->
# ExceptionMiddleware -> router. Registered @app.exception_handler
# handlers live on ExceptionMiddleware, which is INSIDE this middleware
# (only reachable via call_next) — an exception raised HERE, before
# call_next runs, never passes through ExceptionMiddleware at all, so
# it would surface as a bare 500 instead of the friendly page. Rendering
# the response directly, right where the check happens, sidesteps that
# entirely. (Rate limiting, in app/core/rate_limit.py, doesn't have this
# problem — its checks run from inside route handlers, which ARE inside
# ExceptionMiddleware's scope, so RateLimitExceededException correctly
# reaches its @app.exception_handler in main.py.)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        is_new_token = cookie_token is None
        # Same cookie-timing lesson learned the hard way in Batch B's OTP
        # flow: a cookie set on THIS response isn't visible via
        # request.cookies when THIS SAME request later renders a
        # template. So on a first visit, generate the token now and hand
        # it to the route/template via request.state — csrf_field()
        # (core/templates.py) reads state first, cookie second — rather
        # than relying on the cookie the route handler can't see yet.
        effective_token = cookie_token or generate_csrf_token()
        request.state.csrf_token = effective_token

        if request.method in _UNSAFE_METHODS and request.url.path not in EXEMPT_PATHS:
            content_type = request.headers.get("content-type", "")
            submitted_token = None
            if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
                # IMPORTANT: read body() BEFORE form(). Starlette's
                # BaseHTTPMiddleware replays a request body to the route
                # handler downstream ONLY when `request._body` was
                # populated (i.e. something called request.body()) — its
                # own form parser (request.form()) reads the raw ASGI
                # stream directly and does NOT set `_body`, so calling
                # form() first would drain the stream with nothing cached
                # to replay, and the route handler's Form(...)/UploadFile
                # dependencies would see an entirely empty body (every
                # field reported "missing"). request.body() itself caches
                # into `_body`, and request.stream() — which the form
                # parser uses internally — checks for that cache first, so
                # calling body() first makes form() "free" (no second
                # network/stream read) AND makes the body correctly replay
                # downstream. Order matters here; do not swap these two
                # lines without re-verifying against the installed
                # Starlette version's BaseHTTPMiddleware internals.
                await request.body()
                form = await request.form()
                submitted_token = form.get(CSRF_FORM_FIELD)

            if not cookie_token or not submitted_token or submitted_token != cookie_token:
                # Imported lazily to avoid a module-load cycle with
                # core/templates.py (which itself imports from core/csrf.py).
                from app.core.templates import templates

                return templates.TemplateResponse(
                    request, "errors/csrf_failed.html", {"lang": "en"}, status_code=400
                )

        response = await call_next(request)

        # Issue the cookie on first visit (or if it was ever cleared) —
        # every subsequent GET keeps refreshing the same value rather
        # than rotating it, so a form rendered a while ago is still
        # valid when it's finally submitted.
        if is_new_token:
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=effective_token,
                httponly=True,  # the server renders the matching form field from request.state, not JS — see core/csrf.py
                samesite="lax",
                secure=settings.cookie_secure_effective,
                max_age=60 * 60 * 24 * 30,  # 30 days — a long-lived anti-CSRF token, not a session credential
            )

        return response
