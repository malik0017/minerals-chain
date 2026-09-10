"""
app/models/order.py

BRD §6.6 (Order Management):
  - "The system shall support a defined order status lifecycle from
    creation through completion (e.g., pending confirmation, confirmed,
    in transit, delivered, invoiced, completed)"
  - "Upon seller confirmation of an order, both parties' true company
    identities shall become visible to each other for the first time"
  - "A buyer shall confirm receipt to finalize order completion"

Status simplification: BRD's example list includes "invoiced" as a
distinct stage — that's dropped here. Real invoicing (ZATCA e-invoice
generation, VAT, QR codes) is Phase 3 scope in full; modeling a status
value for a document type that doesn't exist yet would just be an
unreachable state with nothing behind it. Five stages instead of six:
PENDING_CONFIRMATION -> CONFIRMED -> IN_TRANSIT -> DELIVERED -> COMPLETED.

No explicit "reject" path for a seller who can't fulfill after
quoting. A real gap, not a forgotten one — deferred the same way
dispute handling is deferred to Phase 3, rather than bolted on here
without the cancellation/refund implications being thought through.

Doesn't duplicate fields from RFQ/Quotation — an Order references both
by FK and reads mineral/quantity/delivery from the RFQ, price/lead-time
from the Quotation, via relationships. Safe because neither RFQ nor
Quotation are ever edited after creation in this system (see their own
docstrings) — there's no "the order silently changed under us" risk
that would normally justify snapshotting fields onto Order itself.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class OrderStatus(str, enum.Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    COMPLETED = "completed"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rfqs.id"), nullable=False)
    quotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=False, unique=True
    )
    buyer_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    seller_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=OrderStatus.PENDING_CONFIRMATION,
    )

    # confirmed_at is THE identity-reveal trigger — see
    # core/identity_guard.py. Kept as an explicit timestamp (not just
    # inferred from status) for the same reason VerificationRequest and
    # MineralPassport keep reviewed_at: an explicit "when" is a more
    # honest audit trail than reconstructing it from status alone.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rfq: Mapped["RFQ"] = relationship("RFQ", foreign_keys=[rfq_id])
    quotation: Mapped["Quotation"] = relationship("Quotation", foreign_keys=[quotation_id])
    buyer_company: Mapped["Company"] = relationship("Company", foreign_keys=[buyer_company_id])
    seller_company: Mapped["Company"] = relationship("Company", foreign_keys=[seller_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Order {self.id} ({self.status.value})>"
