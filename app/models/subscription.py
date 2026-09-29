"""
app/models/subscription.py
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.company import SubscriptionTier


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    GRACE = "grace"          
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
    subtype: Mapped[str | None] = mapped_column(String(30), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  

    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )

    attributes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expiry_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    change_note: Mapped[str | None] = mapped_column(String(255), nullable=True)

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


class SubscriptionCharge(Base, TimestampMixin):
    __tablename__ = "subscription_charges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount_sar: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vat_amount_sar: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_sar: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|paid|waived|cancelled
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    company: Mapped["Company"] = relationship("Company")
