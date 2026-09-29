"""
app/services/product_service.py

"""
import uuid

from sqlalchemy.orm import Session

from app.core.system_settings import get_setting
from app.models.company import Company
from app.models.md_commercial import Incoterm
from app.models.md_product import ProductMaster
from app.services.subscription_limits import SubscriptionLimitError, check_can_create_listing
from app.models.product import Product, ProductStatus
from app.repositories import product_repository
from app.schemas.product import ProductRequest

_EDITABLE_STATUSES = {ProductStatus.DRAFT, ProductStatus.FAILED_VERIFICATION}


class ProductActionError(ValueError):
    pass


def _apply_catalog_fields(db: Session, product: Product, payload: ProductRequest) -> None:
    if get_setting(db, "require_catalog_product_on_listing") and payload.product_master_id is None:
        raise ProductActionError("Pick a catalog product (the platform requires listings to reference the product master).")
    for name in ("product_master_id", "name_ar", "region_id", "min_order_qty", "incoterm_id",
                 "packaging_type_id", "mine_source_id"):
        setattr(product, name, getattr(payload, name))
    if payload.product_master_id is not None:
        pm = db.get(ProductMaster, payload.product_master_id)
        if pm is None or not pm.is_active or pm.status != "active":
            raise ProductActionError("The selected catalog product is not available.")
        product.name_en = pm.name_en
        product.name_ar = product.name_ar or pm.name_ar
        product.mineral_type = pm.mineral_type.name_en
        if pm.grade is not None and not payload.grade:
            product.grade = pm.grade.name_en
        if pm.default_source_id and product.mine_source_id is None:
            product.mine_source_id = pm.default_source_id
    if product.incoterm_id and not product.trade_terms:
        inc = db.get(Incoterm, product.incoterm_id)
        product.trade_terms = inc.code if inc else None


def create_listing(db: Session, seller_company: Company, payload: ProductRequest, created_by=None) -> Product:
    try:
        check_can_create_listing(db, seller_company) 
    except SubscriptionLimitError as exc:
        raise ProductActionError(str(exc))
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
        created_by_user_id=created_by.id if created_by else None,
    )
    product_repository.create(db, product)
    try:
        _apply_catalog_fields(db, product, payload)
    except ProductActionError:
        db.rollback()
        raise
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
    _apply_catalog_fields(db, product, payload)
    db.commit()
    db.refresh(product)
    return product
