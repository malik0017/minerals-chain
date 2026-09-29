"""
app/modules/admin/users/routes.py
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.permissions import require_admin, require_portal
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
from app.core.templates import templates


@router.get("", name="admin_users_list")
def users_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin("users_view")),
    q: str = "", role: str = "", status: str = "", admin_role: str = "", page: int = 1,
    msg: str | None = None, error: str | None = None,
):
    """Batch Q1: search / filter / paginate (hundreds of users) + bulk actions."""
    from sqlalchemy import or_
    from app.core.listing import paginate, qs
    from app.core.permissions import ADMIN_ROLES, admin_can
    from app.models.company import Company
    query = db.query(User).outerjoin(Company, User.company_id == Company.id)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.full_name.ilike(like), User.email.ilike(like), Company.company_name.ilike(like)))
    if role in {r.value for r in UserRole}:
        query = query.filter(User.role == UserRole(role))
    now = datetime.now(timezone.utc)
    if status == "active":
        query = query.filter(User.is_active.is_(True))
    elif status == "disabled":
        query = query.filter(User.is_active.is_(False))
    elif status == "locked":
        query = query.filter(User.locked_until > now)
    elif status == "no2fa":
        query = query.filter(User.totp_enabled.is_(False))
    if admin_role in ADMIN_ROLES:
        query = query.filter(User.admin_role == admin_role)
    users, total, page, pages = paginate(query.order_by(User.created_at.desc()), page, 30)
    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context.update({
        "users": users, "now": now, "total": total, "page": page, "pages": pages,
        "qs": qs(q=q, role=role, status=status, admin_role=admin_role),
        "f": {"q": q, "role": role, "status": status, "admin_role": admin_role},
        "roles": list(UserRole), "admin_roles": ADMIN_ROLES, "can_manage": admin_can(admin, "users"),
        "msg": msg, "error": error,
    })
    return templates.TemplateResponse(request, "admin/users_list.html", context)


@router.post("/bulk", name="admin_users_bulk")
def users_bulk(request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db),
               admin: User = Depends(require_admin("users"))):
    """Bulk activate / deactivate / unlock / reset password for the ticked users."""
    from urllib.parse import quote
    from app.core.security import hash_password
    from app.models.audit_log import AuditLog
    from app.repositories import audit_log_repository
    action = form.get("action")
    ids = [uuid.UUID(v) for v in form.getlist("user_ids") if v]
    back = str(request.url_for("admin_users_list"))
    if not ids:
        return RedirectResponse(url=f"{back}?error={quote('Tick at least one user.')}", status_code=303)
    new_password = (form.get("new_password") or "").strip()
    if action == "reset_password" and len(new_password) < 8:
        return RedirectResponse(url=f"{back}?error={quote('New password must be at least 8 characters.')}", status_code=303)
    done = 0
    for target in db.query(User).filter(User.id.in_(ids)).all():
        if target.id == admin.id and action == "deactivate":
            continue
        if action == "activate":
            target.is_active = True
        elif action == "deactivate":
            target.is_active = False
        elif action == "unlock":
            target.locked_until, target.failed_login_attempts = None, 0
        elif action == "reset_password":
            target.hashed_password = hash_password(new_password)
            target.locked_until, target.failed_login_attempts = None, 0
        else:
            return RedirectResponse(url=f"{back}?error={quote('Choose an action.')}", status_code=303)
        audit_log_repository.create(db, AuditLog(actor_user_id=admin.id, action=f"user_bulk_{action}",
                                                 target_type="user", target_id=target.id, details=target.email))
        done += 1
    db.commit()
    return RedirectResponse(url=f"{back}?msg={quote(f'{action.replace(chr(95), chr(32)).capitalize()}: {done} user(s) updated.')}", status_code=303)


@router.get("/new", name="admin_user_new")
def user_new(request: Request, db: Session = Depends(get_db),
             admin: User = Depends(require_admin("users")), error: str | None = None):
    """Batch K: add extra users to an existing company (multi-user testing,
    company_role RBAC groundwork) or create another administrator."""
    from app.repositories import company_repository
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/users")
    from app.core.permissions import ADMIN_ROLES
    context.update({"companies": company_repository.list_all(db), "error": error, "admin_roles": ADMIN_ROLES})
    return templates.TemplateResponse(request, "admin/user_new.html", context)


@router.post("/new", name="admin_user_create")
def user_create(request: Request, db: Session = Depends(get_db),
                admin: User = Depends(require_admin("users")),
                full_name: str = Form(...), email: str = Form(...), password: str = Form(...),
                role: str = Form("company"), company_id: str = Form(""), company_role: str = Form("operator"),
                job_title: str = Form(""), admin_role: str = Form("support")):
    from urllib.parse import quote
    from app.services import control_center_service as cc
    try:
        user = cc.create_user(db, admin, full_name=full_name, email=email, password=password,
                              company_id=company_id or None, role=role, company_role=company_role, job_title=job_title,
                              admin_role=admin_role)
    except (cc.ControlCenterError, ValueError) as exc:
        db.rollback()
        return RedirectResponse(url=f"{request.url_for('admin_user_new')}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=request.url_for("admin_user_detail", user_id=user.id), status_code=303)


@router.get("/{user_id}", name="admin_user_detail")
def user_detail(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin("users_view")),
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
    from app.services.control_center_service import impersonation_allowed  # Batch K
    from app.core.permissions import ADMIN_ROLES, admin_can
    context["impersonation_allowed"] = impersonation_allowed(db) and admin_can(admin, "system")
    context["admin_roles"] = ADMIN_ROLES
    context["can_manage"] = admin_can(admin, "users")
    return templates.TemplateResponse(request, "admin/user_detail.html", context)


@router.post("/{user_id}/edit", name="admin_user_edit")
def user_edit(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin("users")),
    full_name: str = Form(...),
    is_active: str = Form(None),
    phone: str = Form(None),
    job_title: str = Form(None),
    company_role: str = Form(None),
    preferred_language: str = Form(None),
    admin_role: str = Form(None),
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)

    is_active_value = True if target.id == admin.id else bool(is_active)

    # Batch Q1: only a super admin may change an administrator's permission level.
    from app.core.permissions import ADMIN_ROLES
    if admin_role and target.role == UserRole.ADMIN and admin_role in ADMIN_ROLES and admin_role != target.admin_role:
        if (admin.admin_role or "super_admin") != "super_admin":
            return RedirectResponse(url=f"{request.url_for('admin_user_detail', user_id=user_id)}?error=Only a super administrator can change admin permission levels.", status_code=303)
        if target.id == admin.id and admin_role != "super_admin":
            return RedirectResponse(url=f"{request.url_for('admin_user_detail', user_id=user_id)}?error=You can't lower your own permission level.", status_code=303)
        from app.models.audit_log import AuditLog
        from app.repositories import audit_log_repository
        audit_log_repository.create(db, AuditLog(actor_user_id=admin.id, action="admin_role_changed", target_type="user",
                                                 target_id=target.id, details=f"{target.admin_role} → {admin_role}"))
        target.admin_role = admin_role
    try:
        update_user(db, target, admin, full_name=full_name, is_active=is_active_value,
                    phone=phone, job_title=job_title, company_role=company_role, preferred_language=preferred_language)
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
    admin: User = Depends(require_admin("users")),
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)
    unlock_user(db, target, admin)
    return RedirectResponse(url=request.url_for("admin_user_detail", user_id=user_id), status_code=303)


@router.post("/{user_id}/reset-password", name="admin_user_reset_password")
def user_reset_password(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin("users")),
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
        reset_password(db, target, admin, new_password)
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
    admin: User = Depends(require_admin("users")),
):
    target = user_repository.get_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url=request.url_for("admin_users_list"), status_code=303)
    admin_disable_totp(db, target, admin)
    return RedirectResponse(url=request.url_for("admin_user_detail", user_id=user_id), status_code=303)
