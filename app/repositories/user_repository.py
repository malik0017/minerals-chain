"""app/repositories/user_repository.py"""

from sqlalchemy.orm import Session
from app.models.user import User

def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def create(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user
