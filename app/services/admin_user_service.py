"""
app/services/admin_user_service.py
"""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


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

    target.full_name = full_name.strip()
    target.is_active = is_active
    db.commit()
    db.refresh(target)
    return target


def unlock_user(db: Session, target: User) -> User:
    target.locked_until = None
    target.failed_login_attempts = 0
    db.commit()
    db.refresh(target)
    return target


def reset_password(db: Session, target: User, new_password: str) -> User:
    if len(new_password) < 8:
        raise AdminUserActionError("Password must be at least 8 characters.")
    target.hashed_password = hash_password(new_password)
    target.locked_until = None
    target.failed_login_attempts = 0
    db.commit()
    db.refresh(target)
    return target


def admin_disable_totp(db: Session, target: User) -> User:
    target.totp_secret = None
    target.totp_enabled = False
    db.commit()
    db.refresh(target)
    return target
