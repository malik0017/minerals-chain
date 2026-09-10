"""
app/repositories/company_repository.py
"""

import uuid
from sqlalchemy.orm import Session
from app.models.company import ApprovalStatus, Company, CompanyRole

def get_by_cr_number(db: Session, cr_number: str) -> Company | None:
    return db.query(Company).filter(Company.cr_number == cr_number).first()


def get_by_id(db: Session, company_id: uuid.UUID) -> Company | None:
    return db.get(Company, company_id)


def list_pending(db: Session) -> list[Company]:
    """The admin approvals queue (Batch 3) — oldest submissions first,
    so nothing sits unreviewed indefinitely just because newer ones
    keep appearing above it."""
    return (
        db.query(Company)
        .filter(Company.status == ApprovalStatus.PENDING)
        .order_by(Company.created_at.asc())
        .all()
    )


def list_all(
    db: Session,
    role: CompanyRole | None = None,
    status: ApprovalStatus | None = None,
) -> list[Company]:
   
    query = db.query(Company)
    if role is not None:
        query = query.filter(Company.role == role)
    if status is not None:
        query = query.filter(Company.status == status)
    return query.order_by(Company.created_at.desc()).all()


def create(db: Session, company: Company) -> Company:
    db.add(company)
    db.flush()  # assigns company.id without committing yet — caller controls the transaction
    return company
