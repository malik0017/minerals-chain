"""
app/models/product_spec.py
"""
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class ProductSpec(Base, TimestampMixin):
    __tablename__ = "product_specs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_parameters.id"), nullable=True
    )
    parameter: Mapped[str] = mapped_column(String(80), nullable=False)
    min_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    test_method: Mapped[str | None] = mapped_column(String(80), nullable=True)

    product: Mapped["Product"] = relationship("Product", back_populates="specs")
    quality_parameter: Mapped["QualityParameter"] = relationship("QualityParameter")

    def __str__(self) -> str:
        return f"{self.parameter} {self.min_value or ''}–{self.max_value or ''} {self.unit or ''}"
