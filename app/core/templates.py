"""
app/core/templates.py

Batch C: every route module used to instantiate its OWN
`Jinja2Templates(directory="app/templates")` — harmless when templates
had no shared configuration, but Jinja2Templates creates a fresh
jinja2.Environment per instance, so registering the `t()` translation
function as a template global on any ONE of those instances would
never reach templates rendered through any of the others (which is
most of them, since header.html/sidebar.html/footer.html are included
into nearly every page regardless of which route rendered it).

One shared instance, imported everywhere instead, fixes this at the
root rather than needing every route file to remember to register its
own globals. Every route module now does
`from app.core.templates import templates` instead of constructing
its own.
"""
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from markupsafe import Markup

from app.core.csrf import CSRF_COOKIE_NAME, CSRF_FORM_FIELD
from app.core.localization import DEFAULT_LANGUAGE, t
from app.core.visual_polish import avatar_class, initials

templates = Jinja2Templates(directory="app/templates")


@pass_context
def _t_template(jinja_context, key: str) -> str:
    """
    The Jinja-facing wrapper around core.localization.t(). Every
    template calls {{ t('some.key') }} with just the key — this
    function is what makes that automatically use the CURRENT
    render's `lang` context variable, via Jinja's pass_context, rather
    than every single template call needing to spell out
    {{ t('some.key', lang) }} explicitly (easy to forget once, silently
    falls back to English every time you do — this wrapper makes that
    class of bug impossible instead of relying on remembering).

    Python-side callers (e.g. core/portal_nav.py, which builds
    nav_items before the template even runs) still call
    core.localization.t(key, lang) directly with an explicit lang —
    this wrapper is only registered as the Jinja global.
    """
    lang = jinja_context.get("lang", DEFAULT_LANGUAGE)
    return t(key, lang)


templates.env.globals["t"] = _t_template

# Batch F: colored-avatar-chip helpers for the "multi-color, professional,
# not plain/simple text" data table pass. See app/core/visual_polish.py.
templates.env.globals["initials"] = initials
templates.env.globals["avatar_class"] = avatar_class


@pass_context
def _csrf_field(jinja_context) -> Markup:
    """
    Batch G: every server-rendered POST form calls {{ csrf_field() }}
    once, right after its opening <form> tag, to get a hidden input
    carrying the anti-CSRF token. Reads request.state.csrf_token first
    (set by CSRFMiddleware for THIS request, including a token that was
    only just generated and isn't in request.cookies yet — the same
    cookie-timing lesson as Batch B's OTP flow), falling back to the
    cookie for safety if state was somehow never set.
    """
    request = jinja_context.get("request")
    token = ""
    if request is not None:
        token = getattr(request.state, "csrf_token", None) or request.cookies.get(CSRF_COOKIE_NAME, "")
    return Markup(f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{token}">')


templates.env.globals["csrf_field"] = _csrf_field
