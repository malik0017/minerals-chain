"""
app/services/avatar_service.py
"""
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.user import User

AVATAR_DIR = Path("app/static/uploads/avatars")
MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class AvatarActionError(ValueError):
    """Raised for any invalid avatar upload. Routes catch this and
    show the message."""
    pass


def save_avatar(db: Session, user: User, file: UploadFile, contents: bytes) -> User:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise AvatarActionError("Please upload a JPG, PNG, or WEBP image.")
    if len(contents) > MAX_AVATAR_BYTES:
        raise AvatarActionError("Image must be 2MB or smaller.")
    if len(contents) == 0:
        raise AvatarActionError("That file appears to be empty.")

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)

    if user.avatar_filename:
        old_path = AVATAR_DIR / user.avatar_filename
        old_path.unlink(missing_ok=True)

    ext = ALLOWED_CONTENT_TYPES[file.content_type]
    new_filename = f"{user.id}-{uuid.uuid4().hex[:8]}.{ext}"
    (AVATAR_DIR / new_filename).write_bytes(contents)

    user.avatar_filename = new_filename
    db.commit()
    db.refresh(user)
    return user


def remove_avatar(db: Session, user: User) -> User:
    if user.avatar_filename:
        (AVATAR_DIR / user.avatar_filename).unlink(missing_ok=True)
        user.avatar_filename = None
        db.commit()
        db.refresh(user)
    return user
