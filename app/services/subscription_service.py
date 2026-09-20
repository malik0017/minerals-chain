"""
app/services/subscription_service.py

Batch A: intentionally minimal. This batch's job is to make
`subscriptions` the real source of truth instead of a bare enum (see
models/subscription.py's docstring) — it does NOT build subscription
management UI, upgrade/downgrade flows, or billing. That's real
BRD §6.11 work (tier-limit enforcement, upgrade/downgrade handling,
grace periods) deserving its own batch once there's a concrete need
driving the enforcement logic, not a guess at it today.

What this batch DOES do: every seller/buyer company gets a real,
open-ended Entry-tier Subscription row the moment they're approved —
so the table is populated from day one and Company.subscription_tier
(the cache) never drifts from it. Labs don't get one — BRD leaves lab
subscription tiers as an open question, and Company.subscription_tier
is already nullable for labs; this follows the same rule.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models.company import Company, CompanyRole, SubscriptionTier
from app.models.subscription import Subscription
from app.repositories import subscription_repository


def create_initial_subscription(db: Session, company: Company) -> Subscription | None:
    """Called from admin_service.approve_company() right after a
    company's status flips to APPROVED. Does not commit — the caller
    commits once, alongside the approval itself."""
    if company.role == CompanyRole.LAB:
        return None

    subscription = Subscription(
        company_id=company.id,
        tier=SubscriptionTier.ENTRY,
        start_date=date.today(),
        end_date=None,  # open-ended — Entry tier has no expiry by default
    )
    subscription_repository.create(db, subscription)
    company.subscription_tier = SubscriptionTier.ENTRY
    return subscription
