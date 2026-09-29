"""
app/services/auth_service.py
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from app.models.company import ApprovalStatus, Company, CompanyRole, SubscriptionTier
from app.models.user import User, UserRole
from app.repositories import company_repository, user_repository
from app.core.security import hash_password, verify_password
from app.core.system_settings import get_setting
from app.schemas.auth import RegisterRequest
from app.services import notification_service
from app.services.document_upload_service import save_company_document

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


def register_new_company_user(
    db: Session,
    payload: RegisterRequest,
    *,
    cr_document_contents: bytes,
    cr_document_ext: str,
    license_document_contents: bytes,
    license_document_ext: str,
    consent_version: str | None = None,
) -> User:
    # --- BRD §6.1: uniqueness / duplicate checks before anything is created ---
    if user_repository.get_by_email(db, payload.email):
        raise RegistrationError("An account with this email already exists.")
    if company_repository.get_by_cr_number(db, payload.cr_number):
        raise RegistrationError("A company with this Commercial Registration number is already registered.")

    company_role, user_role = _ROLE_MAP[payload.role]
    company_id = uuid.uuid4()
    cr_document_filename = save_company_document(company_id, "cr", cr_document_contents, cr_document_ext)
    license_document_filename = save_company_document(company_id, "license", license_document_contents, license_document_ext)

    company = Company(
        id=company_id,
        company_name=payload.company_name,
        role=company_role,
        cr_number=payload.cr_number,
        license_or_accreditation_number=payload.license_or_accreditation_number,
        cr_document_filename=cr_document_filename,
        license_document_filename=license_document_filename,
        status=ApprovalStatus.PENDING, 
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
        # Batch Q1 (PDPL): the registration form requires accepting the privacy notice.
        privacy_consent_at=datetime.now(timezone.utc) if consent_version else None,
        privacy_consent_version=consent_version,
    )
    user_repository.create(db, user)
    from app.services import company_document_service
    company_document_service.register_initial(db, company, user)
    from app.services import credential_check_service
    credential_check_service.auto_check(db, company)

    notification_service.notify_admins(
        db, "approvals", "registration_submitted", "New registration awaiting review",
        f"{company.company_name} ({company_role.value}) registered and is waiting for approval.",
        action_url=f"/admin/approvals/{company.id}", company=company.company_name, role=company_role.value,
    )

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
        threshold = get_setting(db, "max_failed_logins")
        lockout_minutes = get_setting(db, "lockout_minutes")
        if user.failed_login_attempts >= threshold:
            user.locked_until = now + timedelta(minutes=lockout_minutes)
            user.failed_login_attempts = 0
            db.commit()
            raise AuthenticationError(f"Too many failed attempts. This account is now locked for {lockout_minutes} minutes.")
        db.commit()
        raise AuthenticationError("Incorrect email or password.")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    if not user.is_active:
        raise AuthenticationError("This account is disabled. Contact the platform administrator.")

    return user
