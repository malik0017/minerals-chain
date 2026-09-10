"""
app/models/product.py

"""
import enum
import uuid
from decimal import Decimal
from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    UNDER_VERIFICATION = "under_verification"
    VERIFIED = "verified"
    FAILED_VERIFICATION = "failed_verification"
    SUSPENDED = "suspended"


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    seller_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    # --- What it is ---
    mineral_type: Mapped[str] = mapped_column(String(100), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    specifications_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Quantity ---
    quantity_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="MT")

    # --- Pricing (optional — some listings are "contact for price") ---
    price_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    price_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")
    price_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "per MT"

    # --- Trade details ---
    packaging: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trade_terms: Mapped[str | None] = mapped_column(String(150), nullable=True)  # e.g. "FOB Jubail"

    # --- BRD §6.2 status lifecycle ---
    status: Mapped[ProductStatus] = mapped_column(
        SAEnum(ProductStatus, name="product_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ProductStatus.DRAFT,
    )

    seller_company: Mapped["Company"] = relationship("Company", foreign_keys=[seller_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.mineral_type} ({self.status.value}) — company {self.seller_company_id}>"
