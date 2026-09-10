"""app/repositories/quotation_repository.py"""
import uuid

from sqlalchemy.orm import Session

from app.models.quotation import Quotation


def create(db: Session, quotation: Quotation) -> Quotation:
    db.add(quotation)
    db.flush()
    return quotation


def get_by_id(db: Session, quotation_id: uuid.UUID) -> Quotation | None:
    return db.get(Quotation, quotation_id)


def list_for_rfq(db: Session, rfq_id: uuid.UUID) -> list[Quotation]:
    """Sorted by price ascending — the natural default for a buyer
    comparing quotes."""
    return (
        db.query(Quotation)
        .filter(Quotation.rfq_id == rfq_id)
        .order_by(Quotation.price_value.asc())
        .all()
    )


def list_for_seller_company(db: Session, seller_company_id: uuid.UUID) -> list[Quotation]:
    return (
        db.query(Quotation)
        .filter(Quotation.seller_company_id == seller_company_id)
        .order_by(Quotation.created_at.desc())
        .all()
    )


def get_by_rfq_and_seller(db: Session, rfq_id: uuid.UUID, seller_company_id: uuid.UUID) -> Quotation | None:
    """Used to enforce one-quotation-per-seller-per-RFQ (see
    quotation_service.py)."""
    return (
        db.query(Quotation)
        .filter(Quotation.rfq_id == rfq_id, Quotation.seller_company_id == seller_company_id)
        .first()
    )


def count_for_rfq(db: Session, rfq_id: uuid.UUID) -> int:
    return db.query(Quotation).filter(Quotation.rfq_id == rfq_id).count()
