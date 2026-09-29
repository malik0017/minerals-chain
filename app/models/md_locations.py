"""
app/models/md_locations.py
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.md_base import MasterDataMixin


class Region(Base, MasterDataMixin):
    __tablename__ = "regions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="SA")


class MineSource(Base, MasterDataMixin):
    __tablename__ = "mine_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mineral_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mineral_types.id"), nullable=True
    )
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=True)
    owner_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )
    owner_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    license_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    # open_pit | underground | quarry | placer | processing_plant
    extraction_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    country_of_origin: Mapped[str] = mapped_column(String(2), nullable=False, default="SA")

    mineral_type: Mapped["MineralType"] = relationship("MineralType")
    region: Mapped["Region"] = relationship("Region")
    owner_company: Mapped["Company"] = relationship("Company")


class Warehouse(Base, MasterDataMixin):
    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )  # null = platform / third-party logistics warehouse
    region_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("regions.id"), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    national_address: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    capacity_mt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    company: Mapped["Company"] = relationship("Company")
    region: Mapped["Region"] = relationship("Region")
    bins: Mapped[list["WarehouseBin"]] = relationship("WarehouseBin", back_populates="warehouse", passive_deletes="all")


class WarehouseBin(Base, TimestampMixin):
    """Bin codes are unique WITHIN a warehouse (A-01 exists in many warehouses),
    so this table does not use MasterDataMixin's globally-unique code."""
    __tablename__ = "warehouse_bins"
    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="uq_warehouse_bin_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    capacity_mt: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    warehouse: Mapped["Warehouse"] = relationship("Warehouse", back_populates="bins")

    def __str__(self) -> str:
        wh = self.warehouse.code if self.warehouse else "?"
        return f"{wh} / {self.code}"
