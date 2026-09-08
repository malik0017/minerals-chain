"""
app/modules/admin/users/routes.py

Every user on the platform, admin included, with basic edit
(name, active/disabled). Separate from /admin/companies — that page
is about companies and their business data (listings etc); this one
is about individual login accounts.
"""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.permissions import require_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import user_repository
from app.services.admin_user_service import AdminUserActionError, update_user

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="admin_users_list")
def users_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
):
    users = user_repository.list_all(db)
    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context["users"] = users
    return templates.TemplateResponse(request, "admin/users_list.html", context)


@router.get("/{user_id}", name="admin_user_detail")
def user_detail(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    error: str | None = None,
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)

    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/users")
    context.update({"target": target, "error": error, "is_self": target.id == admin.id})
    return templates.TemplateResponse(request, "admin/user_detail.html", context)


@router.post("/{user_id}/edit", name="admin_user_edit")
def user_edit(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    full_name: str = Form(...),
    is_active: str = Form(None),
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)

    # Disabled checkboxes never submit a value — when editing your own
    # account the "active" checkbox is disabled in the template (you
    # can't deactivate yourself), so treat that case as always active
    # rather than reading a value the browser never sent.
    is_active_value = True if target.id == admin.id else bool(is_active)

    try:
        update_user(db, target, admin, full_name=full_name, is_active=is_active_value)
    except AdminUserActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('admin_user_detail', user_id=user_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("admin_user_detail", user_id=user_id), status_code=303)
