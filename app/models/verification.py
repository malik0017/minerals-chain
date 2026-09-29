"""
app/models/verification.py
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class VerificationStatus(str, enum.Enum):
    REQUESTED = "requested"
    SAMPLE_SCHEDULED = "sample_scheduled"
    TESTING_IN_PROGRESS = "testing_in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationRequest(Base, TimestampMixin):
    __tablename__ = "verification_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    lab_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=VerificationStatus.REQUESTED,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_reference: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    collection_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    field_officer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sample_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fee_sar: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    testing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    lab_company: Mapped["Company"] = relationship("Company", foreign_keys=[lab_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VerificationRequest product={self.product_id} lab={self.lab_company_id} ({self.status.value})>"
