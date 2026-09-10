"""
app/modules/admin/passports/routes.py
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
from app.repositories import passport_repository
from app.services.passport_service import PassportActionError, approve_passport, get_pending_passport, reject_passport

router = APIRouter(prefix="/admin/passports", tags=["admin-passports"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="admin_passports_list")
def passports_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
):
    pending = passport_repository.list_pending(db)
    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context["passports"] = pending
    return templates.TemplateResponse(request, "admin/passports_list.html", context)


@router.get("/{passport_id}", name="admin_passport_review")
def passport_review(
    request: Request,
    passport_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    error: str | None = None,
):
    try:
        passport = get_pending_passport(db, passport_id)
    except PassportActionError:
        return RedirectResponse(url=request.url_for("admin_passports_list"), status_code=303)

    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/passports")
    context.update({"passport": passport, "error": error})
    return templates.TemplateResponse(request, "admin/passport_review.html", context)


@router.post("/{passport_id}/approve", name="admin_passport_approve")
def passport_approve(
    request: Request,
    passport_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
):
    try:
        passport = get_pending_passport(db, passport_id)
        approve_passport(db, passport, admin)
    except PassportActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('admin_passport_review', passport_id=passport_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("admin_passports_list"), status_code=303)


@router.post("/{passport_id}/reject", name="admin_passport_reject")
def passport_reject(
    request: Request,
    passport_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    reason: str = Form(...),
):
    try:
        passport = get_pending_passport(db, passport_id)
        reject_passport(db, passport, admin, reason)
    except PassportActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('admin_passport_review', passport_id=passport_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("admin_passports_list"), status_code=303)
