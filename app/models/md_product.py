"""
app/models/md_product.py
"""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.md_base import MasterDataMixin


class ProductMaster(Base, MasterDataMixin):
    __tablename__ = "product_masters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Basic ---
    short_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # raw_material | processed | finished_product | by_product
    product_type: Mapped[str] = mapped_column(String(30), nullable=False, default="raw_material")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Mineral classification ---
    mineral_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mineral_types.id"), nullable=False, index=True
    )
    grade_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("grades.id"), nullable=True)
    particle_size_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("particle_sizes.id"), nullable=True
    )
    quality_class: Mapped[str | None] = mapped_column(String(10), nullable=True)  # A / B / C
    chemical_formula: Mapped[str | None] = mapped_column(String(40), nullable=True)
    color: Mapped[str | None] = mapped_column(String(40), nullable=True)
    processing_method: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # --- Source / regulatory ---
    origin_country: Mapped[str] = mapped_column(String(2), nullable=False, default="SA")
    default_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mine_sources.id"), nullable=True
    )
    hs_code_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("hs_codes.id"), nullable=True)
    sds_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hazard_class: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # --- Commercial flags (SAP B1 style) ---
    is_sales_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_purchase_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_inventory_item: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    standard_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    selling_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")

    # --- Inventory / UOM ---
    base_uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True
    )
    purchase_uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True
    )
    sales_uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True
    )
    batch_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True
    )

    # --- Quality ---
    coa_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    inspection_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Logistics ---
    bulk_density_t_m3: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    loading_type: Mapped[str | None] = mapped_column(String(40), nullable=True)   # tipper, tanker, container
    transport_requirements: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- Status: active | inactive | blocked | discontinued ---
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    mineral_type: Mapped["MineralType"] = relationship("MineralType")
    grade: Mapped["Grade"] = relationship("Grade")
    particle_size: Mapped["ParticleSize"] = relationship("ParticleSize")
    default_source: Mapped["MineSource"] = relationship("MineSource")
    hs_code: Mapped["HSCode"] = relationship("HSCode")
    base_uom: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure", foreign_keys=[base_uom_id])
    purchase_uom: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure", foreign_keys=[purchase_uom_id])
    sales_uom: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure", foreign_keys=[sales_uom_id])
    default_warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    packagings: Mapped[list["ProductMasterPackaging"]] = relationship(
        "ProductMasterPackaging", back_populates="product_master", cascade="all, delete-orphan"
    )
    applications: Mapped[list["ProductMasterApplication"]] = relationship(
        "ProductMasterApplication", back_populates="product_master", cascade="all, delete-orphan"
    )


class ProductMasterPackaging(Base, TimestampMixin):
    __tablename__ = "product_master_packagings"
    __table_args__ = (UniqueConstraint("product_master_id", "packaging_type_id", name="uq_pm_packaging"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_master_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_masters.id"), nullable=False, index=True
    )
    packaging_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packaging_types.id"), nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    product_master: Mapped["ProductMaster"] = relationship("ProductMaster", back_populates="packagings")
    packaging_type: Mapped["PackagingType"] = relationship("PackagingType")

    def __str__(self) -> str:
        return f"{self.product_master.code if self.product_master else '?'} · {self.packaging_type.code if self.packaging_type else '?'}"


class ProductMasterApplication(Base, TimestampMixin):
    __tablename__ = "product_master_applications"
    __table_args__ = (UniqueConstraint("product_master_id", "application_id", name="uq_pm_application"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_master_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_masters.id"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)

    product_master: Mapped["ProductMaster"] = relationship("ProductMaster", back_populates="applications")
    application: Mapped["Application"] = relationship("Application")

    def __str__(self) -> str:
        return f"{self.product_master.code if self.product_master else '?'} · {self.application.code if self.application else '?'}"
