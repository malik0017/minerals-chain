"""
app/modules/admin/approvals/routes.py

Every route here is behind require_portal(UserRole.ADMIN) — only real
admins, no preview bypass (that's only for VIEWING other portals, not
the reverse).
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
from app.repositories import company_repository
from app.services.admin_service import AdminActionError, approve_company, reject_company

router = APIRouter(prefix="/admin/approvals", tags=["admin-approvals"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="admin_approvals_list")
def approvals_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
):
    pending = company_repository.list_pending(db)
    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context["companies"] = pending
    return templates.TemplateResponse(request, "admin/approvals_list.html", context)


@router.get("/{company_id}", name="admin_approvals_review")
def approvals_review(
    request: Request,
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    error: str | None = None,
):
    company = company_repository.get_by_id(db, company_id)
    if company is None:
        return RedirectResponse(url=request.url_for("admin_approvals_list"), status_code=303)

    primary_user = company.users[0] if company.users else None

    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context.update({"company": company, "primary_user": primary_user, "error": error})
    return templates.TemplateResponse(request, "admin/approvals_review.html", context)


@router.post("/{company_id}/approve", name="admin_approvals_approve")
def approvals_approve(
    request: Request,
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
):
    try:
        approve_company(db, company_id, admin)
    except AdminActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('admin_approvals_review', company_id=company_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("admin_approvals_list"), status_code=303)


@router.post("/{company_id}/reject", name="admin_approvals_reject")
def approvals_reject(
    request: Request,
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    reason: str = Form(...),
):
    try:
        reject_company(db, company_id, admin, reason)
    except AdminActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('admin_approvals_review', company_id=company_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("admin_approvals_list"), status_code=303)
