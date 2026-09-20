"""
app/services/certification_service.py

Batch A: the single place that creates/approves/rejects a
Certification, for both credential types:
  - lab_certificate: created by verification_service.issue_certificate()
    once a VerificationRequest passes — see create_lab_certificate().
  - mineral_passport: requested directly by a seller on a VERIFIED
    product, reviewed by admin — request_passport() / approve_passport()
    / reject_passport(), same shape as the old passport_service.py.

VALIDITY_PERIOD_DAYS is carried over unchanged from the old
passport_service.py — still a hardcoded constant, still no
admin-configurable policy UI; see the original module's reasoning,
which still applies.
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
from app.repositories import audit_log_repository, certification_repository, notification_repository

VALIDITY_PERIOD_DAYS = 365


class CertificationActionError(ValueError):
    """Raised for any invalid certification action. Routes catch this
    and show the message."""
    pass


def _notify_company_users(db: Session, company: Company, *, type_: str, title: str, body: str) -> None:
    for user in company.users:
        notification_repository.create(
            db, Notification(user_id=user.id, type=type_, title=title, body=body)
        )


# --- Lab certificates (called from verification_service.issue_certificate) ---

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
    )
    certification_repository.create(db, certification)
    certification_repository.create_scope(db, CertificationScope(certification_id=certification.id, product_id=product.id))
    return certification


# --- Mineral passports ---

def request_passport(db: Session, product: Product, category: str) -> Certification:
    if product.status != ProductStatus.VERIFIED:
        raise CertificationActionError("Only a verified listing can request a Mineral Passport.")
    if certification_repository.has_pending_or_active(db, product.id, CertificationType.MINERAL_PASSPORT):
        raise CertificationActionError("This listing already has a pending or currently valid passport.")

    certification = Certification(
        cert_type=CertificationType.MINERAL_PASSPORT,
        name="Mineral Passport",
        category=category,
        subject_company_id=product.seller_company_id,
        status=CertificationStatus.PENDING,
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
    certification.expiry_date = date.today() + timedelta(days=VALIDITY_PERIOD_DAYS)
    certification.reviewed_by_user_id = admin.id
    certification.reviewed_at = datetime.now(timezone.utc)

    product_name = certification.scopes[0].product.mineral_type if certification.scopes else "your listing"
    _notify_company_users(
        db, certification.subject_company,
        type_="passport_approved",
        title="Mineral Passport issued",
        body=f"Your {certification.category.replace('_', ' ')} passport for {product_name} "
             f"has been issued: {certification.certificate_number} (valid until {certification.expiry_date}).",
    )

    # Batch G: BRD §6.8 asks for full admin-action visibility — passport
    # approve/reject was the gap called out in PROJECT_STATUS.md (only
    # company approve/reject was logged before this batch).
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
