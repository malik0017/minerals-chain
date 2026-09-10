"""app/repositories/product_repository.py"""
import uuid
from sqlalchemy.orm import Session
from app.models.product import Product, ProductStatus

def create(db: Session, product: Product) -> Product:
    db.add(product)
    db.flush()
    return product


def get_by_id(db: Session, product_id: uuid.UUID) -> Product | None:
    return db.get(Product, product_id)


def list_for_company(db: Session, company_id: uuid.UUID) -> list[Product]:
    return (
        db.query(Product)
        .filter(Product.seller_company_id == company_id)
        .order_by(Product.created_at.desc())
        .all()
    )


def count_all(db: Session) -> int:
    """Batch 8 — platform-wide total, used for the admin's aggregate
    view when previewing the Seller Portal (no single company to
    scope to)."""
    return db.query(Product).count()


def count_by_status(db: Session, status: ProductStatus) -> int:
    return db.query(Product).filter(Product.status == status).count()


def list_verified(db: Session, search: str | None = None) -> list[Product]:
  
    query = db.query(Product).filter(Product.status == ProductStatus.VERIFIED)
    if search:
        query = query.filter(Product.mineral_type.ilike(f"%{search.strip()}%"))
    return query.order_by(Product.updated_at.desc()).all()


def get_verified_by_id(db: Session, product_id: uuid.UUID) -> Product | None:
    product = db.get(Product, product_id)
    if product is None or product.status != ProductStatus.VERIFIED:
        return None
    return product
