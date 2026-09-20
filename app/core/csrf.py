"""
app/core/csrf.py

Batch G: CSRF protection via the double-submit cookie pattern — no new
dependency (no starlette-csrf, no session middleware), consistent with
this project's existing preference for signed-cookie state over adding
libraries (see the OTP tokens in core/security.py).

How it works:
  1. CSRFMiddleware (registered in main.py) ensures every response
     carries an `mc_csrf` cookie: a random, unguessable token, generated
     once and then reused for the life of the browser session (it is
     NOT rotated per-request — rotating it would break a user with two
     tabs open, one of which submits a form after the other refreshed
     the token).
  2. Every server-rendered POST form includes a hidden `csrf_token`
     field carrying that SAME value, via the `csrf_field()` Jinja
     global registered in core/templates.py.
  3. On every unsafe-method request (POST/PUT/PATCH/DELETE), the
     middleware compares the submitted form's `csrf_token` field against
     the `mc_csrf` cookie. A cross-site form (the attack this defends
     against) can forge the POST body but — by same-origin policy —
     cannot read the victim's `mc_csrf` cookie to put the matching value
     in it, so the two values won't match and the request is rejected.

This is "double-submit" specifically because the token travels via TWO
channels (cookie + form field) that an attacker can't both control —
simpler than a server-side per-session token store, and needs no
session/storage layer this app doesn't otherwise have.
"""
import secrets

CSRF_COOKIE_NAME = "mc_csrf"
CSRF_FORM_FIELD = "csrf_token"

# Paths where this middleware never runs the double-submit CHECK. GET/HEAD/
# OPTIONS are already skipped in the middleware itself (they're not supposed
# to mutate state); this set exists for API-shaped endpoints if any are ever
# added that authenticate a different way (e.g. a bearer token) rather than
# the session cookie. Empty today — nothing in this app fits that yet, but
# the seam matters more than the current membership.
EXEMPT_PATHS: set[str] = set()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
