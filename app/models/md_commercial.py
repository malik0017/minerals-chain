"""
app/models/md_commercial.py
"""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.md_base import MasterDataMixin


class Application(Base, MasterDataMixin):
    __tablename__ = "applications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class CustomerSegment(Base, MasterDataMixin):
    __tablename__ = "customer_segments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class HSCode(Base, MasterDataMixin):
    __tablename__ = "hs_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    national_tariff_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    customs_duty_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    sds_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hazard_class: Mapped[str | None] = mapped_column(String(40), nullable=True)  # GHS / UN class
    export_license_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Incoterm(Base, MasterDataMixin):
    __tablename__ = "incoterms"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition: Mapped[str] = mapped_column(String(10), nullable=False, default="2020")


class PaymentTerm(Base, MasterDataMixin):
    __tablename__ = "payment_terms"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SubscriptionPlan(Base, MasterDataMixin):
    """code is the SubscriptionTier value ("entry" / "mid" / "premium")."""
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annual_price_sar: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    max_active_listings: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = unlimited
    max_active_rfqs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    search_priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expedited_passport_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority_lab_scheduling: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    analytics_level: Mapped[str] = mapped_column(String(20), nullable=False, default="basic")
    dedicated_support: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    grace_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14)
