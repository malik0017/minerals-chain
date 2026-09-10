"""
app/services/two_factor_service.py
"""
import pyotp
from sqlalchemy.orm import Session

from app.models.user import User

ISSUER_NAME = "Minerals Chain"


class TwoFactorActionError(ValueError):
    """Raised for any invalid 2FA setup/confirm/disable action. Routes
    catch this and show the message."""
    pass


def start_enrollment(db: Session, user: User) -> str:
   
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.commit()
    db.refresh(user)
    return secret


def get_provisioning_uri(user: User) -> str:
    if not user.totp_secret:
        raise TwoFactorActionError("No 2FA setup in progress.")
    return pyotp.TOTP(user.totp_secret).provisioning_uri(name=user.email, issuer_name=ISSUER_NAME)


def verify_code(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


def confirm_enrollment(db: Session, user: User, code: str) -> User:
    if not user.totp_secret:
        raise TwoFactorActionError("No 2FA setup in progress — start setup again.")
    if not verify_code(user.totp_secret, code):
        raise TwoFactorActionError("That code didn't match. Check your authenticator app and try again.")
    user.totp_enabled = True
    db.commit()
    db.refresh(user)
    return user


def disable_totp(db: Session, user: User) -> User:
    user.totp_secret = None
    user.totp_enabled = False
    db.commit()
    db.refresh(user)
    return user
