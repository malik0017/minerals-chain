"""
app/models/order.py
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class OrderStatus(str, enum.Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    INVOICED = "invoiced"     
    DISPUTED = "disputed"    
    RESOLVED = "resolved"     
    CANCELLED = "cancelled"   


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

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_reference: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")
    subtotal_sar: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    vat_rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    vat_amount_sar: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    total_value_sar: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    delivery_location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    required_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    incoterm_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    identity_revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settlement_fee_buyer_sar: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    settlement_fee_seller_sar: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    settlement_fee_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_via_dispute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invoice_number: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    invoiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rfq: Mapped["RFQ"] = relationship("RFQ", foreign_keys=[rfq_id])
    documents: Mapped[list["OrderDocument"]] = relationship("OrderDocument", back_populates="order")
    settlement_fees: Mapped[list["SettlementFee"]] = relationship("SettlementFee", back_populates="order")
    quotation: Mapped["Quotation"] = relationship("Quotation", foreign_keys=[quotation_id])
    buyer_company: Mapped["Company"] = relationship("Company", foreign_keys=[buyer_company_id])
    seller_company: Mapped["Company"] = relationship("Company", foreign_keys=[seller_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Order {self.id} ({self.status.value})>"


class RevealLog(Base):
    __tablename__ = "reveal_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    buyer_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    seller_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False)  # "seller_confirmation" | "admin"
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    revealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderDocument(Base, TimestampMixin):
    __tablename__ = "order_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # --- Batch P1 ---
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    visible_to_buyer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    visible_to_seller: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    order: Mapped["Order"] = relationship("Order", back_populates="documents")
    uploaded_by: Mapped["User"] = relationship("User")


class SettlementFeeStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    WAIVED = "waived"      


class SettlementFee(Base, TimestampMixin):
    __tablename__ = "settlement_fees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    paid_by_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    party: Mapped[str] = mapped_column(String(10), nullable=False)  # buyer | seller
    amount_sar: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vat_rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_amount_sar: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_sar: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[SettlementFeeStatus] = mapped_column(
        SAEnum(SettlementFeeStatus, name="settlement_fee_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SettlementFeeStatus.PENDING,
    )
    gateway: Mapped[str | None] = mapped_column(String(30), nullable=True)   # moyasar | hyperpay | manual
    gateway_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    order: Mapped["Order"] = relationship("Order", back_populates="settlement_fees")
    paid_by_company: Mapped["Company"] = relationship("Company")
