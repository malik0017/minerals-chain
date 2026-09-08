"""
app/core/auth.py
"""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.exceptions import NotAuthenticatedException
from app.core.security import decode_access_token
from app.database.base import get_db
from app.models.user import User

SESSION_COOKIE_NAME = "mc_session"

def _load_user_from_request(request: Request, db: Session) -> User | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None

    user_id = decode_access_token(token)
    if not user_id:
        return None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        return None

    return user


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    return _load_user_from_request(request, db)


def get_current_user_required(
    request: Request, db: Session = Depends(get_db)
) -> User:
    user = _load_user_from_request(request, db)
    if user is None:
        raise NotAuthenticatedException()
    return user
