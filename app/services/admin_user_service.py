"""
app/services/admin_user_service.py
"""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories import audit_log_repository


class AdminUserActionError(ValueError):
    """Raised for any invalid admin user-management action."""
    pass


def update_user(
    db: Session, target: User, acting_admin: User, *, full_name: str, is_active: bool,
    phone: str | None = None, job_title: str | None = None, company_role: str | None = None,
    preferred_language: str | None = None,
) -> User:
    if not full_name.strip():
        raise AdminUserActionError("Full name cannot be blank.")
    if target.id == acting_admin.id and not is_active:
        raise AdminUserActionError("You can't deactivate your own account.")

    previous_active = target.is_active
    target.full_name = full_name.strip()
    target.is_active = is_active
    if phone is not None:
        target.phone = phone.strip() or None
    if job_title is not None:
        target.job_title = job_title.strip() or None
    if company_role is not None:
        if company_role not in ("owner", "manager", "operator", "viewer"):
            raise AdminUserActionError("Invalid company role.")
        target.company_role = company_role
    if preferred_language in ("en", "ar"):
        target.preferred_language = preferred_language

    if previous_active != is_active:
        audit_log_repository.create(
            db,
            AuditLog(
                actor_user_id=acting_admin.id,
                action="user_activated" if is_active else "user_deactivated",
                target_type="user",
                target_id=target.id,
            ),
        )

    db.commit()
    db.refresh(target)
    return target


def unlock_user(db: Session, target: User, acting_admin: User) -> User:
    target.locked_until = None
    target.failed_login_attempts = 0

    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=acting_admin.id,
            action="user_unlocked",
            target_type="user",
            target_id=target.id,
        ),
    )

    db.commit()
    db.refresh(target)
    return target


def reset_password(db: Session, target: User, acting_admin: User, new_password: str) -> User:
    if len(new_password) < 8:
        raise AdminUserActionError("Password must be at least 8 characters.")
    target.hashed_password = hash_password(new_password)
    target.locked_until = None
    target.failed_login_attempts = 0

    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=acting_admin.id,
            action="user_password_reset",
            target_type="user",
            target_id=target.id,
        ),
    )

    db.commit()
    db.refresh(target)
    return target


def admin_disable_totp(db: Session, target: User, acting_admin: User) -> User:
    target.totp_secret = None
    target.totp_enabled = False

    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=acting_admin.id,
            action="user_2fa_disabled",
            target_type="user",
            target_id=target.id,
        ),
    )

    db.commit()
    db.refresh(target)
    return target
