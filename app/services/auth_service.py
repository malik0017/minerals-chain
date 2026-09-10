"""
app/services/auth_service.py
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from app.models.company import ApprovalStatus, Company, CompanyRole, SubscriptionTier
from app.models.user import User, UserRole
from app.repositories import company_repository, user_repository
from app.core.security import hash_password, verify_password
from app.schemas.auth import RegisterRequest

_ROLE_MAP = {
    "seller": (CompanyRole.SELLER, UserRole.SELLER),
    "buyer": (CompanyRole.BUYER, UserRole.BUYER),
    "lab": (CompanyRole.LAB, UserRole.LAB),
}

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=30)


class RegistrationError(ValueError):
    pass


class AuthenticationError(ValueError):
    pass


def register_new_company_user(db: Session, payload: RegisterRequest) -> User:
    # --- BRD §6.1: uniqueness / duplicate checks before anything is created ---
    if user_repository.get_by_email(db, payload.email):
        raise RegistrationError("An account with this email already exists.")
    if company_repository.get_by_cr_number(db, payload.cr_number):
        raise RegistrationError("A company with this Commercial Registration number is already registered.")

    company_role, user_role = _ROLE_MAP[payload.role]

    company = Company(
        company_name=payload.company_name,
        role=company_role,
        cr_number=payload.cr_number,
        license_or_accreditation_number=payload.license_or_accreditation_number,
        status=ApprovalStatus.PENDING,  # BRD §6.1: every new registration starts pending
        subscription_tier=SubscriptionTier.ENTRY if company_role != CompanyRole.LAB else None,
        contact_email=payload.email,
        contact_phone=payload.contact_phone,
    )
    company_repository.create(db, company)

    user = User(
        company_id=company.id,
        full_name=payload.full_name,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        role=user_role,
        is_active=True,
    )
    user_repository.create(db, user)

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = user_repository.get_by_email(db, email)
    if user is None:
        raise AuthenticationError("Incorrect email or password.")

    now = datetime.now(timezone.utc)

    if user.locked_until is not None:
        if user.locked_until > now:
            remaining_minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
            raise AuthenticationError(
                f"Too many failed attempts. This account is locked for another {remaining_minutes} minute(s)."
            )
        # Lock has expired — auto-unlock and fall through to a normal check.
        user.locked_until = None
        user.failed_login_attempts = 0

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
            user.locked_until = now + LOCKOUT_DURATION
            user.failed_login_attempts = 0
            db.commit()
            raise AuthenticationError("Too many failed attempts. This account is now locked for 30 minutes.")
        db.commit()
        raise AuthenticationError("Incorrect email or password.")

    # Correct password — reset the counter regardless of what happens next.
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    if not user.is_active:
        raise AuthenticationError("This account is disabled. Contact the platform administrator.")

    return user
