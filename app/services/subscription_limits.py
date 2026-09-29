"""
app/services/subscription_limits.py
"""
from sqlalchemy.orm import Session

from app.core.system_settings import get_setting
from app.models.company import Company
from app.models.md_commercial import SubscriptionPlan
from app.models.product import Product, ProductStatus
from app.models.rfq import RFQ, RFQStatus

class SubscriptionLimitError(ValueError):
    pass


def _plan(db: Session, company: Company) -> SubscriptionPlan | None:
    if company.subscription_tier is None:
        return None
    return db.query(SubscriptionPlan).filter(
        SubscriptionPlan.code == company.subscription_tier.value, SubscriptionPlan.is_active.is_(True)).first()


def check_can_create_listing(db: Session, company: Company) -> None:
    if not get_setting(db, "enforce_subscription_limits"):
        return
    plan = _plan(db, company)
    if plan is None or plan.max_active_listings is None:
        return
    active = db.query(Product).filter(Product.seller_company_id == company.id,
                                      Product.status != ProductStatus.SUSPENDED).count()
    if active >= plan.max_active_listings:
        raise SubscriptionLimitError(
            f"Your {plan.name_en} plan allows {plan.max_active_listings} active listings. "
            "Archive a listing or upgrade your plan to add another.")


def check_can_create_rfq(db: Session, company: Company) -> None:
    if not get_setting(db, "enforce_subscription_limits"):
        return
    plan = _plan(db, company)
    if plan is None or plan.max_active_rfqs is None:
        return
    active = db.query(RFQ).filter(RFQ.buyer_company_id == company.id, RFQ.status == RFQStatus.OPEN).count()
    if active >= plan.max_active_rfqs:
        raise SubscriptionLimitError(
            f"Your {plan.name_en} plan allows {plan.max_active_rfqs} open RFQs. "
            "Close one or upgrade your plan to create another.")
