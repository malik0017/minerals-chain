"""app/repositories/platform_settings_repository.py"""
from sqlalchemy.orm import Session

from app.models.platform_settings import PlatformSettings

SETTINGS_ROW_ID = 1


def get_settings(db: Session) -> PlatformSettings:
    """
    Always returns the one settings row, creating it with every field at
    its safe default the first time anything asks for it (fresh DB, or a
    DB from before this batch's migration ran the row-seed). Never
    returns None, so every caller can just read attributes off the result.
    """
    row = db.get(PlatformSettings, SETTINGS_ROW_ID)
    if row is None:
        row = PlatformSettings(id=SETTINGS_ROW_ID)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def update_settings(db: Session, **fields) -> PlatformSettings:
    row = get_settings(db)
    for key, value in fields.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row
