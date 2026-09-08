"""
app/modules/shared/routes.py

"Shared" because every portal (seller/buyer/lab/admin) uses the same
notifications list. portal_role = the viewer's own role here — no
admin-preview concept on this page.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_required
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User
from app.repositories import notification_repository

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
