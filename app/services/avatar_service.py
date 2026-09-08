"""
app/services/avatar_service.py

Handles profile picture upload for the "My Profile" page. Files are
stored on local disk under app/static/uploads/avatars/ — the same
StaticFiles mount that already serves everything else under /static/
serves these too, no extra wiring needed. This is fine for a single-
server dev/early-production setup; if this app ever runs on multiple
app servers behind a load balancer, avatars would need to move to
shared/object storage (S3 etc.) instead — noted here since it's an
easy thing to trip over later, not because it needs solving now.
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

    # Delete any previous avatar file first — the extension may differ
    # from the new upload, so this can't just be an overwrite.
    if user.avatar_filename:
        old_path = AVATAR_DIR / user.avatar_filename
        old_path.unlink(missing_ok=True)

    ext = ALLOWED_CONTENT_TYPES[file.content_type]
    # A fresh random filename per upload (not just user.id) means an old
    # cached copy in someone's browser can never collide with a new one.
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
