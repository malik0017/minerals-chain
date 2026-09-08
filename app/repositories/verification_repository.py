"""app/repositories/verification_repository.py"""
import uuid

from sqlalchemy.orm import Session

from app.models.verification import VerificationRequest, VerificationStatus

_ACTIVE_STATUSES = (VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED, VerificationStatus.TESTING_IN_PROGRESS)


def create(db: Session, request: VerificationRequest) -> VerificationRequest:
    db.add(request)
    db.flush()
    return request


def get_by_id(db: Session, request_id: uuid.UUID) -> VerificationRequest | None:
    return db.get(VerificationRequest, request_id)


def list_for_lab_company(db: Session, lab_company_id: uuid.UUID) -> list[VerificationRequest]:
    return (
        db.query(VerificationRequest)
        .filter(VerificationRequest.lab_company_id == lab_company_id)
        .order_by(VerificationRequest.created_at.desc())
        .all()
    )


def list_for_product(db: Session, product_id: uuid.UUID) -> list[VerificationRequest]:
    return (
        db.query(VerificationRequest)
        .filter(VerificationRequest.product_id == product_id)
        .order_by(VerificationRequest.created_at.desc())
        .all()
    )


def has_active_request(db: Session, product_id: uuid.UUID) -> bool:
    """Used to stop a seller from filing a second verification request
    on a product that already has one in flight."""
    return (
        db.query(VerificationRequest)
        .filter(VerificationRequest.product_id == product_id, VerificationRequest.status.in_(_ACTIVE_STATUSES))
        .first()
        is not None
    )


def count_all(db: Session) -> int:
    """Batch 8 — platform-wide total, used for the admin's aggregate
    view when previewing the Lab Portal (no single company to scope
    to)."""
    return db.query(VerificationRequest).count()


def count_active(db: Session) -> int:
    return db.query(VerificationRequest).filter(VerificationRequest.status.in_(_ACTIVE_STATUSES)).count()
