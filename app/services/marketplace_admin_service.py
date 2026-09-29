"""
app/services/marketplace_admin_service.py
"""
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.product import Product, ProductStatus
from app.models.user import User
from app.services import notification_service

class MarketplaceAdminError(ValueError):
    pass


def suspend_product(db: Session, product: Product, admin: User, reason: str) -> None:
    if product.status == ProductStatus.SUSPENDED:
        raise MarketplaceAdminError("This listing is already suspended.")
    if len((reason or "").strip()) < 5:
        raise MarketplaceAdminError("Give a reason (shown to the seller).")
    product.status_before_suspension = product.status.value
    product.suspended_reason = reason.strip()
    product.status = ProductStatus.SUSPENDED
    notification_service.notify_company(
        db, product.seller_company, "product_suspended", "Listing suspended",
        f"Your {product.mineral_type} listing was suspended by the platform. Reason: {product.suspended_reason}",
        action_url=f"/seller/listings/{product.id}", mineral=product.mineral_type, reason=product.suspended_reason)
    db.add(AuditLog(actor_user_id=admin.id, action="product_suspended", target_type="product", target_id=product.id,
                    details=f"{product.mineral_type}: {product.suspended_reason}"[:500]))
    db.commit()


def reactivate_product(db: Session, product: Product, admin: User) -> None:
    if product.status != ProductStatus.SUSPENDED:
        raise MarketplaceAdminError("Only a suspended listing can be reactivated.")
    try:
        product.status = ProductStatus(product.status_before_suspension or ProductStatus.DRAFT.value)
    except ValueError:
        product.status = ProductStatus.DRAFT
    product.status_before_suspension = None
    product.suspended_reason = None
    notification_service.notify_company(
        db, product.seller_company, "product_reactivated", "Listing reactivated",
        f"Your {product.mineral_type} listing was reactivated.", action_url=f"/seller/listings/{product.id}",
        mineral=product.mineral_type)
    db.add(AuditLog(actor_user_id=admin.id, action="product_reactivated", target_type="product", target_id=product.id,
                    details=f"{product.mineral_type} → {product.status.value}"))
    db.commit()
