"""
app/services/profile_service.py
"""
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.profile import PasswordChangeRequest, ProfileUpdateRequest


class ProfileActionError(ValueError):
    """Raised for any invalid profile action. Routes catch this and
    show the message."""
    pass


def update_profile(db: Session, user: User, payload: ProfileUpdateRequest) -> User:
    user.full_name = payload.full_name
    db.commit()
    db.refresh(user)
    return user


def change_password(db: Session, user: User, payload: PasswordChangeRequest) -> User:
    if not verify_password(payload.current_password, user.hashed_password):
        raise ProfileActionError("Current password is incorrect.")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return user
