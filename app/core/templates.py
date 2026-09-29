"""
app/core/templates.py
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
    lang = jinja_context.get("lang", DEFAULT_LANGUAGE)
    return t(key, lang)


templates.env.globals["t"] = _t_template
templates.env.globals["initials"] = initials
templates.env.globals["avatar_class"] = avatar_class


@pass_context
def _csrf_field(jinja_context) -> Markup:
    request = jinja_context.get("request")
    token = ""
    if request is not None:
        token = getattr(request.state, "csrf_token", None) or request.cookies.get(CSRF_COOKIE_NAME, "")
    return Markup(f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{token}">')


templates.env.globals["csrf_field"] = _csrf_field

def _dev_banner_enabled() -> bool:
    from app.core.system_settings import get_setting_cached
    return bool(get_setting_cached("dev_mode_banner"))


templates.env.globals["dev_banner_enabled"] = _dev_banner_enabled

def _nav_notifications(request) -> dict:
    empty = {"unread": 0, "entries": []}
    if request is None:
        return empty
    from app.core.auth import SESSION_COOKIE_NAME
    from app.core.security import decode_access_token
    from app.database.base import SessionLocal
    from app.models.user import User
    from app.services.notification_service import header_summary
    user_id = decode_access_token(request.cookies.get(SESSION_COOKIE_NAME, "") or "")
    if not user_id:
        return empty
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None:
            return empty
        return header_summary(db, user.id, user.preferred_language)
    except Exception:
        return empty
    finally:
        db.close()


templates.env.globals["nav_notifications"] = _nav_notifications

from app.core.simple_markup import render as _simple_markup  # noqa: E402

templates.env.filters["markup"] = _simple_markup


def _spec_range(lo, hi, unit=None) -> str:
    from app.services.spec_service import range_label
    return range_label(lo, hi, unit)


templates.env.globals["spec_range"] = _spec_range


def _combine_stack(s: dict) -> dict:
    return {"type": "bar", "stack": "total", "barMaxWidth": 26, "emphasis": {"focus": "series"}, **s}


def _as_line(s: dict, area: bool = False, stack: bool = False) -> dict:
    out = {"type": "line", "smooth": True, "symbolSize": 5, **s}
    if area:
        out["areaStyle"] = {"opacity": 0.15}
    if stack:
        out["stack"] = "total"
    return out


templates.env.filters["combine_stack"] = _combine_stack
templates.env.filters["as_line"] = _as_line

from jinja2 import pass_context  # noqa: E402

_CHART_KEYS = {"name", "text", "formatter_label"}


def _chart_i18n(ctx, option):
    if ctx.get("lang", DEFAULT_LANGUAGE) != "ar":
        return option
    from app.core.translation import translate_text

    def walk(v, key=None):
        if isinstance(v, dict):
            return {k: walk(x, k) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x, key) for x in v]
        if isinstance(v, str) and key in ("name", "text", "data"):
            return translate_text(v)
        return v
    return walk(option)


templates.env.filters["chart_i18n"] = pass_context(_chart_i18n)


@pass_context
def _tr(ctx, value):
    """Translate a Python-side string (e.g. flash text) for Arabic pages."""
    if ctx.get("lang", DEFAULT_LANGUAGE) != "ar" or not isinstance(value, str):
        return value
    from app.core.translation import translate_text
    return translate_text(value)


templates.env.filters["tr"] = _tr
