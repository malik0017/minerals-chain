"""
app/models/subscription.py

BRD §6.11: "The system must associate each company account with
exactly one active subscription tier at any given time" and must
track expiry/grace-period/renewal behavior. A bare enum column on
Company can't represent any of that — no start/end dates, no history
of what tier a company was on last quarter, no per-company overrides.

This table is the real source of truth. Company.subscription_tier
(see its docstring) stays as a fast-access cache of "what tier is
this company on right now" — reading it avoids a join on every page
that needs to check a limit, but every write goes through
subscription_service.py, which updates both together. Never write one
without the other.

`attributes` (JSONB) exists for the "attributes" BRD calls for without
over-specifying today what any of them are — BRD's illustrative
permissions matrix (§6.11) lists things like "priority placement" and
"expedited review" that aren't tied to real enforcement logic yet.
Rather than adding narrow boolean columns for features that don't
exist, a flexible bag here lets a specific company's subscription
carry a one-off override (e.g. a negotiated custom listing limit)
without a schema change — and a real feature migrates OUT of here
into its own column once there's actual enforcement code reading it.
"""
import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.company import SubscriptionTier


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    tier: Mapped[SubscriptionTier] = mapped_column(
        SAEnum(SubscriptionTier, name="subscription_tier", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # Free-text plan variant (e.g. "annual", "monthly") — deliberately not an enum yet;
    # there's no commercial billing cadence defined in BRD to lock into a fixed set.
    subtype: Mapped[str | None] = mapped_column(String(30), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # null = open-ended (e.g. entry tier default)

    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )

    attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])

    @property
    def is_currently_active(self) -> bool:
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        if self.end_date is not None and date.today() > self.end_date:
            return False
        return True

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Subscription {self.tier.value} for company {self.company_id} ({self.status.value})>"
