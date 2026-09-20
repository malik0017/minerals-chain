"""app/repositories/certification_repository.py"""
import uuid

from sqlalchemy.orm import Session

from app.models.certification import Certification, CertificationScope, CertificationStatus, CertificationType


def create(db: Session, certification: Certification) -> Certification:
    db.add(certification)
    db.flush()
    return certification


def create_scope(db: Session, scope: CertificationScope) -> CertificationScope:
    db.add(scope)
    db.flush()
    return scope


def get_by_id(db: Session, certification_id: uuid.UUID) -> Certification | None:
    return db.get(Certification, certification_id)


def get_by_number(db: Session, certificate_number: str) -> Certification | None:
    return db.query(Certification).filter(Certification.certificate_number == certificate_number).first()


def get_by_verification_request_id(db: Session, verification_request_id: uuid.UUID) -> Certification | None:
    return (
        db.query(Certification)
        .filter(Certification.verification_request_id == verification_request_id)
        .first()
    )


def list_for_product(db: Session, product_id: uuid.UUID, cert_type: CertificationType | None = None) -> list[Certification]:
    """Certifications scoped to one product — via CertificationScope.
    Used for a product's verification/passport history."""
    query = (
        db.query(Certification)
        .join(CertificationScope, CertificationScope.certification_id == Certification.id)
        .filter(CertificationScope.product_id == product_id)
    )
    if cert_type is not None:
        query = query.filter(Certification.cert_type == cert_type)
    return query.order_by(Certification.created_at.desc()).all()


def list_for_subject_company(db: Session, subject_company_id: uuid.UUID, cert_type: CertificationType | None = None) -> list[Certification]:
    query = db.query(Certification).filter(Certification.subject_company_id == subject_company_id)
    if cert_type is not None:
        query = query.filter(Certification.cert_type == cert_type)
    return query.order_by(Certification.created_at.desc()).all()


def list_for_issuing_company(db: Session, issuing_company_id: uuid.UUID) -> list[Certification]:
    return (
        db.query(Certification)
        .filter(Certification.issuing_company_id == issuing_company_id)
        .order_by(Certification.created_at.desc())
        .all()
    )


def list_pending(db: Session, cert_type: CertificationType | None = None) -> list[Certification]:
    query = db.query(Certification).filter(Certification.status == CertificationStatus.PENDING)
    if cert_type is not None:
        query = query.filter(Certification.cert_type == cert_type)
    return query.order_by(Certification.created_at.asc()).all()


def has_pending_or_active(db: Session, product_id: uuid.UUID, cert_type: CertificationType) -> bool:
    """Stops a seller from filing a second passport/verification request
    while one is pending, or while an approved-and-unexpired one
    already covers this product."""
    from datetime import date

    existing = (
        db.query(Certification)
        .join(CertificationScope, CertificationScope.certification_id == Certification.id)
        .filter(CertificationScope.product_id == product_id, Certification.cert_type == cert_type)
        .filter(
            (Certification.status == CertificationStatus.PENDING)
            | (
                (Certification.status == CertificationStatus.APPROVED)
                & ((Certification.expiry_date.is_(None)) | (Certification.expiry_date >= date.today()))
            )
        )
        .first()
    )
    return existing is not None
