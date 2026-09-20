"""app/repositories/subscription_repository.py"""
import uuid

from sqlalchemy.orm import Session

from app.models.subscription import Subscription, SubscriptionStatus


def create(db: Session, subscription: Subscription) -> Subscription:
    db.add(subscription)
    db.flush()
    return subscription


def get_active_for_company(db: Session, company_id: uuid.UUID) -> Subscription | None:
    return (
        db.query(Subscription)
        .filter(Subscription.company_id == company_id, Subscription.status == SubscriptionStatus.ACTIVE)
        .order_by(Subscription.start_date.desc())
        .first()
    )


def list_for_company(db: Session, company_id: uuid.UUID) -> list[Subscription]:
    return (
        db.query(Subscription)
        .filter(Subscription.company_id == company_id)
        .order_by(Subscription.start_date.desc())
        .all()
    )
