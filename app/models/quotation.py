"""
app/models/quotation.py

BRD §6.5:
  - "Verified sellers whose products match an open RFQ shall be able
    to view and respond with a formal quotation"
  - "The system shall present quotations to the buyer without
    revealing the responding seller's identity"
  - "A buyer shall be able to compare multiple quotations against
    defined criteria (price, lead time, terms, verification status)"
  - "Acceptance of a quotation by the buyer shall formally create an
    order and close the RFQ to further quotations"

That last line is Batch 4's job (order creation doesn't exist yet) —
this batch only covers submit + anonymized compare. `status` is
already modeled with ACCEPTED as a value so Batch 4 doesn't need
another migration, but nothing in this batch ever sets it.

One seller company can only have ONE quotation per RFQ (enforced in
quotation_service.py, not a DB constraint — see its docstring) —
resubmitting isn't a "new quote," it's editing, which isn't built
either; a seller gets one shot per RFQ for now.
"""
import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class QuotationStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"


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

    rfq: Mapped["RFQ"] = relationship("RFQ", foreign_keys=[rfq_id])
    seller_company: Mapped["Company"] = relationship("Company", foreign_keys=[seller_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Quotation {self.price_currency} {self.price_value} for RFQ {self.rfq_id}>"
