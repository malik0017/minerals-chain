import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

TRANSPORT_MODES = {"truck": "Truck", "rail": "Rail", "sea": "Sea freight", "multimodal": "Multimodal"}
SHIPMENT_STATUSES = {
    "dispatched": "Dispatched",
    "in_transit": "In transit",
    "at_checkpoint": "At checkpoint",
    "delayed": "Delayed",
    "arrived": "Arrived at site",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}
OPEN_STATUSES = ("dispatched", "in_transit", "at_checkpoint", "delayed", "arrived")


class Shipment(Base, TimestampMixin):
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    seller_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    buyer_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="dispatched")
    transport_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="truck")
    carrier_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    vehicle_plate: Mapped[str | None] = mapped_column(String(30), nullable=True)
    driver_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(150), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(150), nullable=True)
    weighbridge_ticket: Mapped[str | None] = mapped_column(String(60), nullable=True)
    gross_weight_t: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    tare_weight_t: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    received_net_t: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    order: Mapped["Order"] = relationship("Order")
    seller_company: Mapped["Company"] = relationship("Company", foreign_keys=[seller_company_id])
    buyer_company: Mapped["Company"] = relationship("Company", foreign_keys=[buyer_company_id])
    events: Mapped[list["ShipmentEvent"]] = relationship(
        "ShipmentEvent", back_populates="shipment", order_by="ShipmentEvent.occurred_at", cascade="all, delete-orphan")

    @property
    def net_weight_t(self) -> Decimal | None:
        if self.gross_weight_t is None or self.tare_weight_t is None:
            return None
        return self.gross_weight_t - self.tare_weight_t

    @property
    def variance_t(self) -> Decimal | None:
        net = self.net_weight_t
        return None if net is None or self.received_net_t is None else self.received_net_t - net

    @property
    def is_late(self) -> bool:
        from datetime import timezone
        ref = self.delivered_at or datetime.now(timezone.utc)
        return bool(self.eta and ref > self.eta and self.status != "cancelled")


class ShipmentEvent(Base, TimestampMixin):
    __tablename__ = "shipment_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    shipment: Mapped[Shipment] = relationship(Shipment, back_populates="events")
    created_by: Mapped["User"] = relationship("User")
