import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

MOVEMENT_TYPES = {
    "receipt": "Receipt",
    "sale_issue": "Sale issue",
    "adjustment": "Adjustment",
    "transfer_out": "Transfer out",
    "transfer_in": "Transfer in",
    "return": "Customer return",
}


class InventoryMovement(Base, TimestampMixin):
    __tablename__ = "inventory_movements"
    __table_args__ = (Index("ix_inventory_movements_company_product", "company_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    product_master_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_masters.id"), nullable=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True, index=True)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="MT")
    unit_cost_sar: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    transfer_group: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    company: Mapped["Company"] = relationship("Company")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    product: Mapped["Product"] = relationship("Product")
    batch: Mapped["Batch"] = relationship("Batch")
    order: Mapped["Order"] = relationship("Order")
    created_by: Mapped["User"] = relationship("User")

    @property
    def type_label(self) -> str:
        return MOVEMENT_TYPES.get(self.movement_type, self.movement_type)
