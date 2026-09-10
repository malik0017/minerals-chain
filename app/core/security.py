"""
app/core/security.py
"""

from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

ALGORITHM = "HS256"
PENDING_2FA_MINUTES = 5


def hash_password(plain_password: str) -> str:
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)

def create_access_token(*, user_id: str, expires_minutes: int | None = None) -> str:
   
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns the user_id (sub claim) if the token is valid and unexpired, else None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def create_pending_2fa_token(*, user_id: str) -> str:
 
    expire = datetime.now(timezone.utc) + timedelta(minutes=PENDING_2FA_MINUTES)
    payload = {"sub": user_id, "purpose": "2fa_pending", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_pending_2fa_token(token: str) -> str | None:
   
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "2fa_pending":
            return None
        return payload.get("sub")
    except JWTError:
        return None
