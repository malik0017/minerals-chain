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
    return db.query(Product).count()


def count_by_status(db: Session, status: ProductStatus) -> int:
    return db.query(Product).filter(Product.status == status).count()


def list_verified(db: Session, search: str | None = None, region_id=None, product_master_id=None) -> list[Product]:
    from sqlalchemy import String, cast
    from app.models.company import Company
    from app.models.md_commercial import SubscriptionPlan
    query = (db.query(Product)
             .join(Company, Company.id == Product.seller_company_id)
             .outerjoin(SubscriptionPlan, SubscriptionPlan.code == cast(Company.subscription_tier, String))
             .filter(Product.status == ProductStatus.VERIFIED, Product.is_visible_to_buyers.is_(True)))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter((Product.mineral_type.ilike(like)) | (Product.grade.ilike(like)) | (Product.name_en.ilike(like)))
    if region_id:
        query = query.filter(Product.region_id == region_id)
    if product_master_id:
        query = query.filter(Product.product_master_id == product_master_id)
    return query.order_by(SubscriptionPlan.search_priority.desc().nullslast(), Product.updated_at.desc()).all()


def get_verified_by_id(db: Session, product_id: uuid.UUID) -> Product | None:
    product = db.get(Product, product_id)
    if product is None or product.status != ProductStatus.VERIFIED or not product.is_visible_to_buyers:
        return None
    return product
