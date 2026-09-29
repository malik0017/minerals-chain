"""
app/models/product.py

"""
import enum
import uuid
from decimal import Decimal
from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Numeric, String, Text
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

    product_master_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_masters.id"), nullable=True, index=True
    )
    name_en: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(150), nullable=True)
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=True)
    min_order_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    incoterm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("incoterms.id"), nullable=True)
    packaging_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packaging_types.id"), nullable=True
    )
    mine_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mine_sources.id"), nullable=True
    )
    is_visible_to_buyers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    # --- Batch M3: admin suspension (BRD §6.8) — status to restore on reactivation
    suspended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_before_suspension: Mapped[str | None] = mapped_column(String(30), nullable=True)

    seller_company: Mapped["Company"] = relationship("Company", foreign_keys=[seller_company_id])
    product_master: Mapped["ProductMaster"] = relationship("ProductMaster")
    region: Mapped["Region"] = relationship("Region")
    incoterm: Mapped["Incoterm"] = relationship("Incoterm")
    packaging_type: Mapped["PackagingType"] = relationship("PackagingType")
    mine_source: Mapped["MineSource"] = relationship("MineSource")
    specs: Mapped[list["ProductSpec"]] = relationship(
        "ProductSpec", back_populates="product", cascade="all, delete-orphan"
    )

    @property
    def display_name(self) -> str:
        return self.name_en or (self.product_master.name_en if self.product_master else None) or self.mineral_type

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Product {self.mineral_type} ({self.status.value}) — company {self.seller_company_id}>"
