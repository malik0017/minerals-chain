"""app/repositories/order_repository.py"""
import uuid

from sqlalchemy.orm import Session

from app.models.order import Order


def create(db: Session, order: Order) -> Order:
    db.add(order)
    db.flush()
    return order


def get_by_id(db: Session, order_id: uuid.UUID) -> Order | None:
    return db.get(Order, order_id)


def get_by_quotation_id(db: Session, quotation_id: uuid.UUID) -> Order | None:
    return db.query(Order).filter(Order.quotation_id == quotation_id).first()


def list_for_buyer_company(db: Session, buyer_company_id: uuid.UUID) -> list[Order]:
    return (
        db.query(Order)
        .filter(Order.buyer_company_id == buyer_company_id)
        .order_by(Order.created_at.desc())
        .all()
    )


def list_for_seller_company(db: Session, seller_company_id: uuid.UUID) -> list[Order]:
    return (
        db.query(Order)
        .filter(Order.seller_company_id == seller_company_id)
        .order_by(Order.created_at.desc())
        .all()
    )
