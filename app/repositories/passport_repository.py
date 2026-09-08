"""app/repositories/passport_repository.py"""
import uuid

from sqlalchemy.orm import Session

from app.models.passport import MineralPassport, PassportStatus


def create(db: Session, passport: MineralPassport) -> MineralPassport:
    db.add(passport)
    db.flush()
    return passport


def get_by_id(db: Session, passport_id: uuid.UUID) -> MineralPassport | None:
    return db.get(MineralPassport, passport_id)


def get_by_number(db: Session, passport_number: str) -> MineralPassport | None:
    return db.query(MineralPassport).filter(MineralPassport.passport_number == passport_number).first()


def list_for_product(db: Session, product_id: uuid.UUID) -> list[MineralPassport]:
    return (
        db.query(MineralPassport)
        .filter(MineralPassport.product_id == product_id)
        .order_by(MineralPassport.created_at.desc())
        .all()
    )


def list_for_company(db: Session, seller_company_id: uuid.UUID) -> list[MineralPassport]:
    return (
        db.query(MineralPassport)
        .filter(MineralPassport.seller_company_id == seller_company_id)
        .order_by(MineralPassport.created_at.desc())
        .all()
    )


def list_pending(db: Session) -> list[MineralPassport]:
    return (
        db.query(MineralPassport)
        .filter(MineralPassport.status == PassportStatus.PENDING)
        .order_by(MineralPassport.created_at.asc())
        .all()
    )


def has_pending_or_active(db: Session, product_id: uuid.UUID) -> bool:
    """Stops a seller from filing a second passport request while one
    is pending review, or while an approved-and-unexpired one already
    covers this product."""
    from datetime import date

    existing = (
        db.query(MineralPassport)
        .filter(MineralPassport.product_id == product_id)
        .filter(
            (MineralPassport.status == PassportStatus.PENDING)
            | ((MineralPassport.status == PassportStatus.APPROVED) & (MineralPassport.valid_until >= date.today()))
        )
        .first()
    )
    return existing is not None
