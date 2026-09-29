"""
app/services/api_token_service.py
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.api_token import API_SCOPES, ApiToken
from app.models.audit_log import AuditLog
from app.models.company import ApprovalStatus
from app.models.user import User, UserRole

MAX_ACTIVE_PER_USER = 10
EXPIRY_CHOICES = {"30": 30, "90": 90, "365": 365, "never": None}


class ApiTokenError(ValueError):
    pass


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue(db: Session, user: User, name: str, scopes: list[str], expiry: str = "90") -> tuple[ApiToken, str]:
    name = (name or "").strip()[:100]
    if len(name) < 2:
        raise ApiTokenError("Give the token a name (e.g. “Field tablet”).")
    scopes = [s for s in scopes if s in API_SCOPES] or ["read"]
    if "write" in scopes and "read" not in scopes:
        scopes.insert(0, "read")
    if expiry not in EXPIRY_CHOICES:
        raise ApiTokenError("Choose an expiry.")
    active = [t for t in db.query(ApiToken).filter(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None)).all() if t.is_active]
    if len(active) >= MAX_ACTIVE_PER_USER:
        raise ApiTokenError(f"You already have {MAX_ACTIVE_PER_USER} active tokens — revoke one first.")
    prefix = secrets.token_hex(4)
    raw = f"mc_{prefix}_{secrets.token_urlsafe(32)}"
    days = EXPIRY_CHOICES[expiry]
    token = ApiToken(user_id=user.id, name=name, prefix=prefix, token_hash=_hash(raw), scopes=scopes,
                     expires_at=datetime.now(timezone.utc) + timedelta(days=days) if days else None)
    db.add(token)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="api_token_created", target_type="user", target_id=user.id,
                    details=f"{name} [{','.join(scopes)}] mc_{prefix}_…"))
    db.commit()
    return token, raw


def revoke(db: Session, token: ApiToken, actor: User) -> None:
    if token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        db.add(AuditLog(actor_user_id=actor.id, action="api_token_revoked", target_type="user", target_id=token.user_id,
                        details=f"{token.name} mc_{token.prefix}_…"))
        db.commit()


def authenticate(db: Session, raw: str, ip: str | None = None) -> tuple[User, ApiToken] | None:
    if not raw or not raw.startswith("mc_"):
        return None
    token = db.query(ApiToken).filter(ApiToken.token_hash == _hash(raw)).first()
    if token is None or not token.is_active:
        return None
    user = token.user
    if user is None or not user.is_active:
        return None
    if user.role != UserRole.ADMIN and (user.company is None or user.company.status != ApprovalStatus.APPROVED):
        return None
    now = datetime.now(timezone.utc)
    if token.last_used_at is None or now - token.last_used_at > timedelta(minutes=1):
        token.last_used_at, token.last_used_ip = now, (ip or "")[:64]
        db.commit()
    return user, token


def for_user(db: Session, user: User) -> list[ApiToken]:
    return db.query(ApiToken).filter(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc()).all()


def get_owned(db: Session, token_id, user: User | None) -> ApiToken | None:
    try:
        t = db.get(ApiToken, uuid.UUID(str(token_id)))
    except ValueError:
        return None
    if t is None or (user is not None and t.user_id != user.id):
        return None
    return t
