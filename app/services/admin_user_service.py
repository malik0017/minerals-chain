"""
app/services/admin_user_service.py

Admin managing individual user accounts — separate from company
approval (admin_service.py). Deliberately narrow: full name and
active/disabled status only. Changing someone's role or email from
here would cross into identity/authorization territory that needs
more care than a quick edit form — not built.
"""
from sqlalchemy.orm import Session

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
