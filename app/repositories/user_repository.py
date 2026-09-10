"""app/repositories/user_repository.py"""

import uuid

from sqlalchemy.orm import Session
from app.models.user import User

def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def list_all(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def create(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user
