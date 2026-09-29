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
REGISTRATION_OTP_MINUTES = 10   
EMAIL_VERIFIED_MINUTES = 30    


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

def create_registration_otp_token(*, email: str, otp_hash: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=REGISTRATION_OTP_MINUTES)
    payload = {"email": email, "otp_hash": otp_hash, "purpose": "registration_otp", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_registration_otp_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "registration_otp":
            return None
        return {"email": payload.get("email"), "otp_hash": payload.get("otp_hash")}
    except JWTError:
        return None


def create_email_verified_token(*, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=EMAIL_VERIFIED_MINUTES)
    payload = {"email": email, "purpose": "email_verified", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_email_verified_token(token: str) -> str | None:
    """Returns the verified email if the token is valid and unexpired, else None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "email_verified":
            return None
        return payload.get("email")
    except JWTError:
        return None

IMPERSONATION_MINUTES = 60


def create_impersonator_token(*, admin_user_id: str, target_user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=IMPERSONATION_MINUTES)
    payload = {"sub": admin_user_id, "target": target_user_id, "purpose": "impersonator", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_impersonator_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "impersonator":
            return None
        return {"admin_id": payload.get("sub"), "target_id": payload.get("target")}
    except JWTError:
        return None
