"""
app/models/rfq.py
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class RFQStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"   


class RFQ(Base, TimestampMixin):
    __tablename__ = "rfqs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    buyer_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    mineral_type: Mapped[str] = mapped_column(String(100), nullable=False)
    specifications_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    quantity_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="MT")

    delivery_location: Mapped[str] = mapped_column(String(150), nullable=False)
    delivery_timeframe: Mapped[str] = mapped_column(String(100), nullable=False)
    commercial_terms_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[RFQStatus] = mapped_column(
        SAEnum(RFQStatus, name="rfq_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=RFQStatus.OPEN,
    )

    # --- Batch J (Schema V1 rfqs alignment) ---
    rfq_reference: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    product_master_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_masters.id"), nullable=True
    )
    grade_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("grades.id"), nullable=True)
    required_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    incoterm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("incoterms.id"), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # --- Batch M3: cancellation
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    buyer_company: Mapped["Company"] = relationship("Company", foreign_keys=[buyer_company_id])
    incoterm: Mapped["Incoterm"] = relationship("Incoterm")
    product_master: Mapped["ProductMaster"] = relationship("ProductMaster")
    grade: Mapped["Grade"] = relationship("Grade")
    specs: Mapped[list["RFQSpec"]] = relationship("RFQSpec", back_populates="rfq", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RFQ {self.mineral_type} ({self.status.value}) — buyer {self.buyer_company_id}>"


class RFQSpec(Base, TimestampMixin):
    """Batch J — Schema V1 `rfq_specs`: the buyer's required range for one
    parameter. Used by quotation matching (match_score) in Batch M."""
    __tablename__ = "rfq_specs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rfqs.id"), nullable=False, index=True)
    parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_parameters.id"), nullable=True
    )
    parameter: Mapped[str] = mapped_column(String(80), nullable=False)
    min_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    rfq: Mapped["RFQ"] = relationship("RFQ", back_populates="specs")
