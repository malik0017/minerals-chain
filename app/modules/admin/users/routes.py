"""
app/modules/admin/users/routes.py
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.permissions import require_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import user_repository
from app.services.admin_user_service import (
    AdminUserActionError,
    admin_disable_totp,
    reset_password,
    unlock_user,
    update_user,
)

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
    context["now"] = datetime.now(timezone.utc)
    return templates.TemplateResponse(request, "admin/users_list.html", context)


@router.get("/{user_id}", name="admin_user_detail")
def user_detail(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    error: str | None = None,
    reset_success: bool = False,
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)

    now = datetime.now(timezone.utc)
    is_locked = target.locked_until is not None and target.locked_until > now
    locked_minutes_remaining = (
        max(1, int((target.locked_until - now).total_seconds() // 60) + 1) if is_locked else 0
    )

    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/users")
    context.update({
        "target": target, "error": error, "is_self": target.id == admin.id, "reset_success": reset_success,
        "is_locked": is_locked, "locked_minutes_remaining": locked_minutes_remaining,
    })
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


@router.post("/{user_id}/unlock", name="admin_user_unlock")
def user_unlock(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)
    unlock_user(db, target)
    return RedirectResponse(url=request.url_for("admin_user_detail", user_id=user_id), status_code=303)


@router.post("/{user_id}/reset-password", name="admin_user_reset_password")
def user_reset_password(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)

    if new_password != confirm_password:
        return RedirectResponse(
            url=f"{request.url_for('admin_user_detail', user_id=user_id)}?error=Passwords do not match.",
            status_code=303,
        )
    try:
        reset_password(db, target, new_password)
    except AdminUserActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('admin_user_detail', user_id=user_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"{request.url_for('admin_user_detail', user_id=user_id)}?reset_success=true", status_code=303
    )


@router.post("/{user_id}/disable-2fa", name="admin_user_disable_2fa")
def user_disable_2fa(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)
    admin_disable_totp(db, target)
    return RedirectResponse(url=request.url_for("admin_user_detail", user_id=user_id), status_code=303)
