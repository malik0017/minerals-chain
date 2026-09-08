"""app/repositories/notification_repository.py"""
import uuid
from sqlalchemy.orm import Session
from app.models.notification import Notification

def create(db: Session, notification: Notification) -> Notification:
    db.add(notification)
    db.flush()
    return notification

def list_for_user(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )

def count_unread(db: Session, user_id: uuid.UUID) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .count()
    )