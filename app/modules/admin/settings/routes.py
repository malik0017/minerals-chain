"""
app/modules/admin/settings/routes.py
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.permissions import require_admin, require_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.repositories import audit_log_repository, platform_settings_repository

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])
from app.core.templates import templates


@router.get("", name="admin_settings")
def settings_form(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin("settings")),
    saved: bool = False,
):
    platform_settings = platform_settings_repository.get_settings(db)
    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context.update({"platform_settings": platform_settings, "saved": saved})
    return templates.TemplateResponse(request, "admin/settings.html", context)


@router.post("", name="admin_settings_update")
def settings_update(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin("settings")),
    registration_enabled_seller: str = Form(None),
    registration_enabled_buyer: str = Form(None),
    registration_enabled_lab: str = Form(None),
    require_email_otp: str = Form(None),
):
    updated = platform_settings_repository.update_settings(
        db,
        registration_enabled_seller=bool(registration_enabled_seller),
        registration_enabled_buyer=bool(registration_enabled_buyer),
        registration_enabled_lab=bool(registration_enabled_lab),
        require_email_otp=bool(require_email_otp),
    )
    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=admin.id,
            action="platform_settings_updated",
            target_type="platform_settings",
            target_id=admin.id,
            details=(
                f"seller={updated.registration_enabled_seller} "
                f"buyer={updated.registration_enabled_buyer} "
                f"lab={updated.registration_enabled_lab} "
                f"require_email_otp={updated.require_email_otp}"
            ),
        ),
    )
    db.commit()
    return RedirectResponse(url=f"{request.url_for('admin_settings')}?saved=true", status_code=303)
