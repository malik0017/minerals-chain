"""
app/services/certification_service.py
"""
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.certification import Certification, CertificationScope, CertificationStatus, CertificationType
from app.models.company import Company
from app.models.notification import Notification
from app.models.product import Product, ProductStatus
from app.models.user import User
from app.models.verification import VerificationRequest
from app.services import notification_service
from app.repositories import audit_log_repository, certification_repository, notification_repository
from app.core.system_settings import get_setting

VALIDITY_PERIOD_DAYS = 365


class CertificationActionError(ValueError):
    """Raised for any invalid certification action. Routes catch this
    and show the message."""
    pass


def _notify_company_users(db: Session, target_company: Company, *, type_: str, title: str, body: str,
                           action_url: str | None = None, **params) -> None:
    # Batch M6: bilingual, deep-linked — see services/notification_service.py
    notification_service.notify_company(db, target_company, type_, title, body, action_url=action_url, **params)


def create_lab_certificate(
    db: Session, verification_request: VerificationRequest, lab_user: User, notes: str
) -> Certification:
    """Does NOT commit — verification_service.issue_certificate() commits
    once, after also updating the VerificationRequest/Product status, so
    both changes land in one transaction."""
    product = verification_request.product
    certification = Certification(
        cert_type=CertificationType.LAB_CERTIFICATE,
        name="Certificate of Analysis",
        subject_company_id=product.seller_company_id,
        issuing_company_id=verification_request.lab_company_id,
        verification_request_id=verification_request.id,
        issued_by_user_id=lab_user.id,
        certificate_number=f"COA-{secrets.token_hex(4).upper()}",
        notes=notes,
        issue_date=date.today(),
        status=CertificationStatus.APPROVED,
        reviewed_at=datetime.now(timezone.utc),
        signed_off_at=datetime.now(timezone.utc),
        signed_off_by_user_id=lab_user.id,
        test_completed_at=date.today(),
    )
    coa_days = get_setting(db, "coa_validity_days")
    if coa_days:
        certification.expiry_date = date.today() + timedelta(days=coa_days)
    verification_request.completed_at = datetime.now(timezone.utc)
    certification_repository.create(db, certification)
    certification_repository.create_scope(db, CertificationScope(certification_id=certification.id, product_id=product.id))
    return certification


# --- Mineral passports ---

def request_passport(db: Session, product: Product, category: str) -> Certification:
    if product.status != ProductStatus.VERIFIED:
        raise CertificationActionError("Only a verified listing can request a Mineral Passport.")
    existing = certification_repository.list_for_product(db, product.id, cert_type=CertificationType.MINERAL_PASSPORT)
    if any(c.status == CertificationStatus.PENDING for c in existing):
        raise CertificationActionError("This listing already has a pending passport request.")
    active = next((c for c in existing if c.is_currently_valid), None)
    renewal_of = None
    if active is not None:
        window = get_setting(db, "passport_renewal_window_days")
        if active.expiry_date is None or (active.expiry_date - date.today()).days > window:
            raise CertificationActionError(
                f"This listing already has a valid passport. Renewal opens {window} days before it expires.")
        renewal_of = active
    tier = getattr(product.seller_company, "subscription_tier", None)
    expedited = bool(tier) and getattr(tier, "value", str(tier)) == "premium"

    certification = Certification(
        cert_type=CertificationType.MINERAL_PASSPORT,
        name="Mineral Passport",
        category=category,
        subject_company_id=product.seller_company_id,
        status=CertificationStatus.PENDING,
        fee_sar=get_setting(db, "passport_fee_standard_sar" if category == "domestic" else "passport_fee_export_sar"),
        source_certification_id=next(
            (c.id for c in certification_repository.list_for_product(db, product.id, cert_type=CertificationType.LAB_CERTIFICATE)
             if c.status == CertificationStatus.APPROVED), None),
        renewal_of_id=renewal_of.id if renewal_of else None,
        is_expedited=expedited,
    )
    certification_repository.create(db, certification)
    certification_repository.create_scope(db, CertificationScope(certification_id=certification.id, product_id=product.id))
    db.commit()
    db.refresh(certification)
    return certification


def get_pending_certification(db: Session, certification_id: uuid.UUID) -> Certification:
    certification = certification_repository.get_by_id(db, certification_id)
    if certification is None:
        raise CertificationActionError("Certification not found.")
    return certification


def approve_passport(db: Session, certification: Certification, admin: User) -> Certification:
    if certification.status != CertificationStatus.PENDING:
        raise CertificationActionError(f"This passport request is already {certification.status.value}.")

    certification.status = CertificationStatus.APPROVED
    certification.certificate_number = f"MP-{secrets.token_hex(4).upper()}"
    certification.issue_date = date.today()
    start = date.today()
    if certification.renewal_of_id:
        prev = db.get(Certification, certification.renewal_of_id)
        if prev is not None and prev.expiry_date and prev.expiry_date > start:
            start = prev.expiry_date
    certification.expiry_date = start + timedelta(days=get_setting(db, "passport_validity_days"))
    certification.reviewed_by_user_id = admin.id
    certification.reviewed_at = datetime.now(timezone.utc)

    product_name = certification.scopes[0].product.mineral_type if certification.scopes else "your listing"
    _notify_company_users(
        db, certification.subject_company,
        type_="passport_approved",
        title="Mineral Passport issued",
        body=f"Your {certification.category.replace('_', ' ')} passport for {product_name} "
             f"has been issued: {certification.certificate_number} (valid until {certification.expiry_date}).",
        mineral=product_name, certificate=certification.certificate_number, until=certification.expiry_date,
    )

    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=admin.id,
            action="passport_approved",
            target_type="certification",
            target_id=certification.id,
            details=certification.certificate_number,
        ),
    )

    db.commit()
    db.refresh(certification)
    return certification


def reject_passport(db: Session, certification: Certification, admin: User, rejection_reason: str) -> Certification:
    if certification.status != CertificationStatus.PENDING:
        raise CertificationActionError(f"This passport request is already {certification.status.value}.")

    certification.status = CertificationStatus.REJECTED
    certification.rejection_reason = rejection_reason
    certification.reviewed_by_user_id = admin.id
    certification.reviewed_at = datetime.now(timezone.utc)

    product_name = certification.scopes[0].product.mineral_type if certification.scopes else "your listing"
    _notify_company_users(
        db, certification.subject_company,
        type_="passport_rejected",
        title="Mineral Passport request not approved",
        body=f"Your passport request for {product_name} was not approved. Reason: {rejection_reason}",
        mineral=product_name, reason=rejection_reason,
    )

    audit_log_repository.create(
        db,
        AuditLog(
            actor_user_id=admin.id,
            action="passport_rejected",
            target_type="certification",
            target_id=certification.id,
            details=rejection_reason,
        ),
    )

    db.commit()
    db.refresh(certification)
    return certification
