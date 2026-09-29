"""
app/modules/shared/routes.py
"""
import uuid
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
    show: str = "all",
    page: int = 1,
):
    from app.models.notification import Notification
    from app.services.notification_service import icon_for, localized
    page = max(1, page)
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if show == "unread":
        q = q.filter(Notification.is_read.is_(False))
    total = q.count()
    rows = q.order_by(Notification.created_at.desc()).offset((page - 1) * 30).limit(30).all()
    items = []
    for n in rows:
        title, body = localized(n, user.preferred_language)
        items.append({"id": n.id, "title": title, "body": body, "is_read": n.is_read, "icon": icon_for(n.type),
                      "action_url": n.action_url, "created_at": n.created_at, "type": n.type})
    context = build_portal_context(user, user.role, active_path=None)
    context.update({"notification_list": items, "show": show, "page": page,
                    "pages": max(1, (total + 29) // 30), "total": total,
                    "unread_total": db.query(Notification).filter(Notification.user_id == user.id,
                                                                  Notification.is_read.is_(False)).count()})
    return templates.TemplateResponse(request, "shared/notifications.html", context)


@router.post("/notifications/read-all", name="notifications_read_all")
def notifications_read_all(request: Request, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user_required)):
    from app.models.notification import Notification
    now = datetime.now(timezone.utc)
    db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read.is_(False)).update(
        {Notification.is_read: True, Notification.read_at: now}, synchronize_session=False)
    db.commit()
    return RedirectResponse(url=request.url_for("notifications_index"), status_code=303)


@router.get("/notifications/{notification_id}/open", name="notification_open")
def notification_open(request: Request, notification_id: uuid.UUID, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user_required)):
    """Mark one notification read and follow its deep link (same-site only)."""
    from app.models.notification import Notification
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        return RedirectResponse(url=request.url_for("notifications_index"), status_code=303)
    if not n.is_read:
        n.is_read, n.read_at = True, datetime.now(timezone.utc)
        db.commit()
    target = n.action_url if (n.action_url or "").startswith("/") and not (n.action_url or "").startswith("//") else "/notifications"
    return RedirectResponse(url=target, status_code=303)


@router.get("/language/set", name="language_set")
def language_set(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
    lang: str = "en",
    next: str = "/",
):
    
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

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
