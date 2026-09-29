"""
app/models/quotation.py
"""
import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class QuotationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"  
    EXPIRED = "expired"     


class Quotation(Base, TimestampMixin):
    __tablename__ = "quotations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rfqs.id"), nullable=False, index=True)
    seller_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    price_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    price_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")
    price_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)

    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    terms_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[QuotationStatus] = mapped_column(
        SAEnum(QuotationStatus, name="quotation_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=QuotationStatus.SUBMITTED,
    )

    quotation_reference: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    coa_certification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certifications.id"), nullable=True
    )
    passport_certification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certifications.id"), nullable=True
    )
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incoterm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("incoterms.id"), nullable=True)
    validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    rfq: Mapped["RFQ"] = relationship("RFQ", foreign_keys=[rfq_id])
    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    incoterm: Mapped["Incoterm"] = relationship("Incoterm")
    seller_company: Mapped["Company"] = relationship("Company", foreign_keys=[seller_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Quotation {self.price_currency} {self.price_value} for RFQ {self.rfq_id}>"
