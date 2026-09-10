"""
app/models/rfq.py

BRD §6.5 (Request for Quotation and Negotiation):
  - "A buyer shall be able to create an RFQ specifying mineral type,
    required specifications, quantity, delivery location, delivery
    timeframe, and commercial terms"
  - "Verified sellers whose products match an open RFQ shall be able
    to view and respond with a formal quotation"
  - "Acceptance of a quotation by the buyer shall formally create an
    order and close the RFQ to further quotations"

Matching model: BRD says "whose products match" — this batch
implements a broadcast model instead of an automated matching engine:
every RFQ is visible to every approved seller in the inbox (Batch 2),
and it's the seller's own judgement whether they can fulfill it. A
real matching algorithm (by mineral type, quantity range, etc.) is a
genuine feature in its own right and would need real usage data to
tune sensibly — not something to guess at now. Easy to add a filter
on top of the broadcast list later without changing this model.

Status: OPEN while accepting quotations, CLOSED once the buyer
accepts one (Batch 3 — quotations don't exist yet, so nothing sets
CLOSED yet in this batch; the enum value exists now so the column
doesn't need another migration when quotations land).
"""
import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class RFQStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


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

    buyer_company: Mapped["Company"] = relationship("Company", foreign_keys=[buyer_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RFQ {self.mineral_type} ({self.status.value}) — buyer {self.buyer_company_id}>"
