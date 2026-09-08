"""app/repositories/certificate_repository.py"""
import uuid

from sqlalchemy.orm import Session

from app.models.certificate import Certificate


def create(db: Session, certificate: Certificate) -> Certificate:
    db.add(certificate)
    db.flush()
    return certificate


def get_by_verification_request_id(db: Session, verification_request_id: uuid.UUID) -> Certificate | None:
    return (
        db.query(Certificate)
        .filter(Certificate.verification_request_id == verification_request_id)
        .first()
    )


def list_for_lab_company(db: Session, lab_company_id: uuid.UUID) -> list[Certificate]:
    """Batch 7 — admin oversight of a lab's issued certificates,
    shown on /admin/companies/{id} for lab companies (BRD §6.8)."""
    return (
        db.query(Certificate)
        .filter(Certificate.lab_company_id == lab_company_id)
        .order_by(Certificate.issued_at.desc())
        .all()
    )
