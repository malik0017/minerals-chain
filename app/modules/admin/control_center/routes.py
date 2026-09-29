"""
app/modules/admin/control_center/routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.auth import IMPERSONATOR_COOKIE_NAME, SESSION_COOKIE_NAME, get_current_user_required
from app.core.config import settings
from app.core.permissions import require_admin, require_portal
from app.core.portal_nav import build_portal_context
from app.core.security import create_access_token, create_impersonator_token, decode_impersonator_token
from app.core import system_settings as ss
from app.core.templates import templates
from app.database.base import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.repositories import audit_log_repository
from app.services import control_center_service as cc

router = APIRouter(tags=["admin-control-center"])


def _to(request: Request, name: str, msg=None, error=None, **params):
    url = str(request.url_for(name, **params))
    q = "&".join(x for x in (f"msg={quote(msg)}" if msg else "", f"error={quote(error)}" if error else "") if x)
    return RedirectResponse(url=url + (f"?{q}" if q else ""), status_code=303)


@router.get("/admin/control-center", name="admin_control_center")
def control_center(request: Request, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin("dashboard")),
                   msg: str | None = None, error: str | None = None):
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/control-center")
    from app.services import analytics_service
    checklist = cc.security_checklist(db)
    context.update({
        "health": cc.system_health(db), "checklist": checklist,
        "impersonation_allowed": cc.impersonation_allowed(db), "msg": msg, "error": error,
        # Batch R2: visual dashboard
        "dash": analytics_service.dashboard(db), "security_score": analytics_service.security_score(checklist),
    })
    return templates.TemplateResponse(request, "admin/control_center.html", context)


@router.post("/admin/control-center/secure-uploads", name="admin_secure_uploads")
def secure_uploads(request: Request, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin("system"))):
    moved = cc.secure_legacy_uploads(db, admin)
    return _to(request, "admin_control_center", msg=f"Moved {moved} document(s) to private storage.")


@router.get("/admin/system-settings", name="admin_system_settings")
def system_settings_page(request: Request, db: Session = Depends(get_db),
                         admin: User = Depends(require_admin("system")),
                         msg: str | None = None, error: str | None = None):
    values = ss.get_all(db)
    groups = [(cat, title, icon, [values[d.key] for d in ss.DEFINITIONS if d.category == cat])
              for cat, (title, icon) in ss.CATEGORIES.items()]
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/system-settings")
    context.update({"groups": groups, "msg": msg, "error": error, "is_production": settings.APP_ENV == "production"})
    return templates.TemplateResponse(request, "admin/system_settings.html", context)


@router.post("/admin/system-settings", name="admin_system_settings_save")
def system_settings_save(request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db),
                               admin: User = Depends(require_admin("system"))):
    category = form.get("_category")
    errors, changes = [], []
    for d in ss.DEFINITIONS:
        if d.category != category:
            continue
        if d.value_type != "bool" and d.key not in form:
            continue 
        try:
            value = ss.validate(d.key, form.get(d.key))
        except ss.SettingValidationError as exc:
            errors.append(str(exc))
            continue
        old, new = ss.set_setting(db, d.key, value, admin.id)
        if old != new:
            changes.append(f"{d.key}: {old} → {new}")
    if errors:
        db.rollback()
        return _to(request, "admin_system_settings", error=" ".join(errors))
    if changes:
        audit_log_repository.create(db, AuditLog(
            actor_user_id=admin.id, action="system_settings_updated", target_type="system_settings",
            target_id=admin.id, details="; ".join(changes)))
    db.commit()
    return _to(request, "admin_system_settings", msg=f"Saved — {len(changes)} change(s)." if changes else "No changes.")


@router.post("/admin/system-settings/{key}/reset", name="admin_system_setting_reset")
def system_setting_reset(request: Request, key: str, db: Session = Depends(get_db),
                         admin: User = Depends(require_admin("system"))):
    try:
        d = ss.definition(key)
    except KeyError:
        return _to(request, "admin_system_settings", error="Unknown setting.")
    old, new = ss.set_setting(db, key, d.default, admin.id)
    audit_log_repository.create(db, AuditLog(
        actor_user_id=admin.id, action="system_setting_reset", target_type="system_settings",
        target_id=admin.id, details=f"{key}: {old} → {new} (default)"))
    db.commit()
    return _to(request, "admin_system_settings", msg=f"{d.label} reset to default.")


@router.post("/admin/impersonate/{user_id}", name="admin_impersonate")
def impersonate(request: Request, user_id: uuid.UUID, db: Session = Depends(get_db),
                admin: User = Depends(require_admin("system"))):
    if not cc.impersonation_allowed(db):
        return _to(request, "admin_user_detail", error="Impersonation is disabled (System Settings → Dev tools).", user_id=user_id)
    target = db.get(User, user_id)
    if target is None or target.role == UserRole.ADMIN or not target.is_active:
        return _to(request, "admin_user_detail", error="Only an active non-admin user can be impersonated.", user_id=user_id)
    audit_log_repository.create(db, AuditLog(
        actor_user_id=admin.id, action="impersonation_started", target_type="user", target_id=target.id,
        details=f"Admin {admin.email} viewing as {target.email}"))
    db.commit()
    response = RedirectResponse(url=request.url_for("home"), status_code=303)
    secure = settings.cookie_secure_effective
    response.set_cookie(SESSION_COOKIE_NAME, create_access_token(user_id=str(target.id), expires_minutes=60),
                        httponly=True, samesite="lax", secure=secure, max_age=3600)
    response.set_cookie(IMPERSONATOR_COOKIE_NAME,
                        create_impersonator_token(admin_user_id=str(admin.id), target_user_id=str(target.id)),
                        httponly=True, samesite="lax", secure=secure, max_age=3600)
    return response


@router.post("/impersonation/stop", name="impersonation_stop")
def stop_impersonation(request: Request, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user_required)):
    data = decode_impersonator_token(request.cookies.get(IMPERSONATOR_COOKIE_NAME, ""))
    admin = db.get(User, uuid.UUID(data["admin_id"])) if data else None
    if admin is None or admin.role != UserRole.ADMIN or not admin.is_active or data["target_id"] != str(user.id):
        response = RedirectResponse(url=request.url_for("login_form"), status_code=303)
        response.delete_cookie(SESSION_COOKIE_NAME)
        response.delete_cookie(IMPERSONATOR_COOKIE_NAME)
        return response
    audit_log_repository.create(db, AuditLog(
        actor_user_id=admin.id, action="impersonation_stopped", target_type="user", target_id=user.id,
        details=f"Admin {admin.email} stopped viewing as {user.email}"))
    db.commit()
    response = RedirectResponse(url=request.url_for("admin_control_center"), status_code=303)
    response.set_cookie(SESSION_COOKIE_NAME, create_access_token(user_id=str(admin.id)), httponly=True,
                        samesite="lax", secure=settings.cookie_secure_effective,
                        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    response.delete_cookie(IMPERSONATOR_COOKIE_NAME)
    return response
