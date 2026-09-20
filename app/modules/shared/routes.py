"""
app/modules/shared/routes.py
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_optional, get_current_user_required
from app.core.config import settings
from app.core.localization import SUPPORTED_LANGUAGES
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User
from app.repositories import notification_repository

router = APIRouter()
from app.core.templates import templates

LANG_COOKIE_NAME = "mc_lang"


@router.get("/notifications", name="notifications_index")
def notifications_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
):
    notifications = notification_repository.list_for_user(db, user.id)

    unread = [n for n in notifications if not n.is_read]
    if unread:
        now = datetime.now(timezone.utc)
        for n in unread:
            n.is_read = True
            n.read_at = now
        db.commit()

    context = build_portal_context(user, user.role, active_path=None)
    context["notification_list"] = notifications
    return templates.TemplateResponse(request, "shared/notifications.html", context)


@router.get("/language/set", name="language_set")
def language_set(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    lang: str = "en",
    next: str = "/",
):
    """
    Batch C: GET rather than POST, deliberately — this is a pure
    preference toggle with no sensitive side effects (unlike, say,
    approving a company), so the usual "state changes should be POST"
    guidance is outweighed here by fitting cleanly into the vendor
    header's existing plain <a> dropdown items without restructuring
    them into forms.

    `next` is only ever used as a same-site redirect target — never
    trust it as an absolute URL (that would be an open-redirect hole).
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    # Only ever redirect within this app — reject anything that looks
    # like it points elsewhere.
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/"

    if user is not None:
        user.preferred_language = lang
        db.commit()

    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(
        key=LANG_COOKIE_NAME, value=lang, max_age=365 * 24 * 60 * 60, samesite="lax",
        secure=settings.cookie_secure_effective,
    )
    return response
