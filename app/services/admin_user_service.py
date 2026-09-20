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
    db: Session, target: User, acting_admin: User, *, full_name: str, is_active: bool
) -> User:
    if not full_name.strip():
        raise AdminUserActionError("Full name cannot be blank.")
    if target.id == acting_admin.id and not is_active:
        raise AdminUserActionError("You can't deactivate your own account.")

    previous_active = target.is_active
    target.full_name = full_name.strip()
    target.is_active = is_active

    # Batch G: only log when something about the account's standing
    # actually changed — a routine "just edited the name" save
    # shouldn't read the same as an activate/deactivate decision.
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

    # Batch G: BRD §6.8 admin-action trail — deliberately no password
    # content or hash in `details`, an admin resetting a password is
    # exactly the kind of high-sensitivity action that needs a WHO/WHEN
    # record without ever logging the credential itself.
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
