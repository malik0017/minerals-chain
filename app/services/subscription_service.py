"""
app/services/subscription_service.py
"""
from datetime import date
from sqlalchemy.orm import Session
from app.models.company import Company, CompanyRole, SubscriptionTier
from app.models.subscription import Subscription
from app.repositories import subscription_repository


def create_initial_subscription(db: Session, company: Company) -> Subscription | None:
    if company.role == CompanyRole.LAB:
        return None

    subscription = Subscription(
        company_id=company.id,
        tier=SubscriptionTier.ENTRY,
        start_date=date.today(),
        end_date=None,  
    )
    subscription_repository.create(db, subscription)
    company.subscription_tier = SubscriptionTier.ENTRY
    return subscription


from datetime import datetime, timedelta, timezone  
from decimal import Decimal  
from app.models.audit_log import AuditLog  
from app.models.md_commercial import SubscriptionPlan  
from app.models.product import Product, ProductStatus  
from app.models.rfq import RFQ, RFQStatus  
from app.models.subscription import SubscriptionCharge, SubscriptionStatus  


class SubscriptionError(ValueError):
    pass


TIER_ORDER = {"entry": 0, "mid": 1, "premium": 2}


def plan_for(db: Session, tier: str | None) -> SubscriptionPlan | None:
    if not tier:
        return None
    return db.query(SubscriptionPlan).filter(SubscriptionPlan.code == tier).first()


def current_subscription(db: Session, company: Company) -> Subscription | None:
    return (db.query(Subscription)
            .filter(Subscription.company_id == company.id,
                    Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE]))
            .order_by(Subscription.start_date.desc(), Subscription.created_at.desc()).first())


def usage(db: Session, company: Company) -> dict:
    return {
        "listings": db.query(Product).filter(Product.seller_company_id == company.id,
                                             Product.status != ProductStatus.SUSPENDED).count(),
        "rfqs": db.query(RFQ).filter(RFQ.buyer_company_id == company.id, RFQ.status == RFQStatus.OPEN).count(),
    }


def status_info(db: Session, company: Company) -> dict:
    sub = current_subscription(db, company)
    tier = company.subscription_tier.value if company.subscription_tier else None
    plan = plan_for(db, tier)
    today = date.today()
    info = {"subscription": sub, "tier": tier, "plan": plan, "status": "none", "end_date": None,
            "grace_until": None, "days_left": None, "usage": usage(db, company)}
    if sub is None:
        return info
    info["status"] = sub.status.value
    info["end_date"] = sub.end_date
    if sub.end_date:
        grace = plan.grace_period_days if plan else 14
        info["grace_until"] = sub.end_date + timedelta(days=grace)
        info["days_left"] = (sub.end_date - today).days
    return info


def _charge(db: Session, company: Company, sub: Subscription, plan: SubscriptionPlan) -> SubscriptionCharge | None:
    from app.core.system_settings import get_setting
    from app.services.reference_service import next_reference
    price = Decimal(plan.annual_price_sar or 0)
    if price <= 0:
        return None
    rate = Decimal(get_setting(db, "vat_rate_pct"))
    vat = (price * rate / 100).quantize(Decimal("0.01"))
    charge = SubscriptionCharge(
        reference=next_reference(db, "subscription"), company_id=company.id, subscription_id=sub.id,
        tier=plan.code, period_start=sub.start_date, period_end=sub.end_date,
        amount_sar=price, vat_amount_sar=vat, total_sar=price + vat, status="pending",
    )
    db.add(charge)
    return charge


def _start(db: Session, company: Company, tier: str, actor, note: str) -> Subscription:
    today = date.today()
    for old in db.query(Subscription).filter(Subscription.company_id == company.id,
                                             Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE])):
        old.status = SubscriptionStatus.CANCELLED
        if old.end_date is None or old.end_date > today:
            old.end_date = today
    sub = Subscription(
        company_id=company.id, tier=SubscriptionTier(tier), start_date=today,
        end_date=None if tier == "entry" else today + timedelta(days=365), status=SubscriptionStatus.ACTIVE,
        changed_by_user_id=actor.id if actor else None, change_note=note[:255],
    )
    db.add(sub)
    db.flush()
    company.subscription_tier = SubscriptionTier(tier)
    company.subscription_valid_until = sub.end_date
    plan = plan_for(db, tier)
    if plan:
        _charge(db, company, sub, plan)
    return sub


def change_plan(db: Session, company: Company, new_tier: str, actor, *, by_admin: bool = False) -> Subscription:
    from app.services import notification_service
    if company.role == CompanyRole.LAB:
        raise SubscriptionError("Laboratories are not on a subscription plan.")
    if new_tier not in TIER_ORDER:
        raise SubscriptionError("Unknown plan.")
    current = company.subscription_tier.value if company.subscription_tier else "entry"
    if new_tier == current and not by_admin:
        raise SubscriptionError("You are already on this plan.")
    target = plan_for(db, new_tier)
    if TIER_ORDER[new_tier] < TIER_ORDER.get(current, 0) and target is not None:
        u = usage(db, company)
        problems = []
        if target.max_active_listings is not None and u["listings"] > target.max_active_listings:
            problems.append(f"{u['listings']} active listings (plan allows {target.max_active_listings})")
        if target.max_active_rfqs is not None and u["rfqs"] > target.max_active_rfqs:
            problems.append(f"{u['rfqs']} open RFQs (plan allows {target.max_active_rfqs})")
        if problems and not by_admin:
            raise SubscriptionError("Can't downgrade yet: you have " + " and ".join(problems)
                                    + ". Archive listings or close RFQs first.")
    sub = _start(db, company, new_tier, actor, f"{current} → {new_tier}" + (" (admin)" if by_admin else ""))
    name = target.name_en if target else new_tier
    notification_service.notify_company(db, company, "subscription_changed", "Subscription plan changed",
                                        f"Your plan is now {name}.", action_url="/account/subscription",
                                        plan=target.name_ar if target and target.name_ar else name)
    if actor is not None:
        db.add(AuditLog(actor_user_id=actor.id, action="subscription_changed", target_type="company",
                        target_id=company.id, details=f"{company.company_name}: {current} → {new_tier}"))
    db.commit()
    return sub


def renew(db: Session, company: Company, actor) -> Subscription:
    tier = company.subscription_tier.value if company.subscription_tier else "entry"
    if tier == "entry":
        raise SubscriptionError("The entry plan does not expire.")
    sub = current_subscription(db, company)
    start = max(date.today(), sub.end_date + timedelta(days=1)) if sub and sub.end_date else date.today()
    new = _start(db, company, tier, actor, "renewal")
    new.start_date, new.end_date = date.today(), start + timedelta(days=365)
    company.subscription_valid_until = new.end_date
    if actor is not None:
        db.add(AuditLog(actor_user_id=actor.id, action="subscription_renewed", target_type="company",
                        target_id=company.id, details=f"{company.company_name}: {tier} until {new.end_date}"))
    db.commit()
    return new


def run_lifecycle(db: Session) -> dict:
    """Idempotent daily job (also run from the admin page and lazily when a
    company opens its subscription page)."""
    from app.core.system_settings import get_setting
    from app.services import notification_service
    today = date.today()
    notice_days = get_setting(db, "subscription_expiry_notice_days")
    stats = {"notified": 0, "grace": 0, "expired": 0}
    subs = db.query(Subscription).filter(Subscription.end_date.isnot(None),
                                         Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.GRACE])).all()
    for sub in subs:
        company = sub.company
        plan = plan_for(db, sub.tier.value)
        name = plan.name_en if plan else sub.tier.value
        grace_until = sub.end_date + timedelta(days=plan.grace_period_days if plan else 14)
        if sub.status == SubscriptionStatus.ACTIVE and today <= sub.end_date and (sub.end_date - today).days <= notice_days \
                and sub.expiry_notified_at is None:
            notification_service.notify_company(db, company, "subscription_expiring", "Subscription expiring soon",
                                                f"Your {name} plan ends on {sub.end_date}. Renew to keep your benefits.",
                                                action_url="/account/subscription", plan=name, until=sub.end_date)
            sub.expiry_notified_at = datetime.now(timezone.utc)
            stats["notified"] += 1
        elif sub.status == SubscriptionStatus.ACTIVE and today > sub.end_date:
            sub.status = SubscriptionStatus.GRACE
            notification_service.notify_company(db, company, "subscription_grace", "Subscription in grace period",
                                                f"Your {name} plan has ended. Grace period until {grace_until}.",
                                                action_url="/account/subscription", plan=name, until=grace_until)
            stats["grace"] += 1
        if sub.status == SubscriptionStatus.GRACE and today > grace_until:
            sub.status = SubscriptionStatus.EXPIRED
            _start(db, company, "entry", None, f"auto-downgrade after {name} expired")
            notification_service.notify_company(db, company, "subscription_expired", "Subscription expired",
                                                f"Your {name} plan expired and you are now on the entry plan.",
                                                action_url="/account/subscription", plan=name)
            stats["expired"] += 1
    db.commit()
    return stats
