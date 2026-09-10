"""app/repositories/rfq_repository.py"""
import uuid

from sqlalchemy.orm import Session

from app.models.rfq import RFQ, RFQStatus


def create(db: Session, rfq: RFQ) -> RFQ:
    db.add(rfq)
    db.flush()
    return rfq


def get_by_id(db: Session, rfq_id: uuid.UUID) -> RFQ | None:
    return db.get(RFQ, rfq_id)


def list_for_company(db: Session, buyer_company_id: uuid.UUID) -> list[RFQ]:
    return (
        db.query(RFQ)
        .filter(RFQ.buyer_company_id == buyer_company_id)
        .order_by(RFQ.created_at.desc())
        .all()
    )


def list_open(db: Session) -> list[RFQ]:
    """Batch 2 — the seller RFQ inbox. Broadcast model: every open RFQ,
    visible to every approved seller (see rfq.py's docstring for why
    there's no matching filter yet)."""
    return (
        db.query(RFQ)
        .filter(RFQ.status == RFQStatus.OPEN)
        .order_by(RFQ.created_at.desc())
        .all()
    )


def count_open(db: Session) -> int:
    return db.query(RFQ).filter(RFQ.status == RFQStatus.OPEN).count()


def count_all(db: Session) -> int:
    """Admin platform-wide aggregate when previewing the Buyer Portal
    (no single company to scope to) — same pattern as
    product_repository.count_all()."""
    return db.query(RFQ).count()
