"""
app/services/product_service.py

"""
import uuid

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.product import Product, ProductStatus
from app.repositories import product_repository
from app.schemas.product import ProductRequest

_EDITABLE_STATUSES = {ProductStatus.DRAFT, ProductStatus.FAILED_VERIFICATION}


class ProductActionError(ValueError):
    pass


def create_listing(db: Session, seller_company: Company, payload: ProductRequest) -> Product:
    product = Product(
        seller_company_id=seller_company.id,
        mineral_type=payload.mineral_type,
        grade=payload.grade,
        specifications_notes=payload.specifications_notes,
        quantity_value=payload.quantity_value,
        quantity_unit=payload.quantity_unit,
        price_value=payload.price_value,
        price_currency=payload.price_currency,
        price_unit=payload.price_unit,
        packaging=payload.packaging,
        trade_terms=payload.trade_terms,
        status=ProductStatus.DRAFT,
    )
    product_repository.create(db, product)
    db.commit()
    db.refresh(product)
    return product


def get_owned_listing(db: Session, product_id: uuid.UUID, seller_company_id: uuid.UUID) -> Product:
    product = product_repository.get_by_id(db, product_id)
    if product is None or product.seller_company_id != seller_company_id:
        raise ProductActionError("Listing not found.")
    return product


def update_listing(db: Session, product: Product, payload: ProductRequest) -> Product:
    if product.status not in _EDITABLE_STATUSES:
        raise ProductActionError(
            f"This listing can't be edited while it's {product.status.value.replace('_', ' ')}."
        )
    product.mineral_type = payload.mineral_type
    product.grade = payload.grade
    product.specifications_notes = payload.specifications_notes
    product.quantity_value = payload.quantity_value
    product.quantity_unit = payload.quantity_unit
    product.price_value = payload.price_value
    product.price_currency = payload.price_currency
    product.price_unit = payload.price_unit
    product.packaging = payload.packaging
    product.trade_terms = payload.trade_terms
    db.commit()
    db.refresh(product)
    return product
