"""
app/models/md_units.py
"""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.md_base import MasterDataMixin


class UnitOfMeasure(Base, MasterDataMixin):
    __tablename__ = "units_of_measure"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # mass | volume | length | percentage | concentration | density | hardness | count | other
    uom_type: Mapped[str] = mapped_column(String(20), nullable=False, default="mass")
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    factor_to_base: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False, default=1)
    is_base: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ParticleSize(Base, MasterDataMixin):
    __tablename__ = "particle_sizes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mesh: Mapped[int | None] = mapped_column(nullable=True)                       # e.g. 325
    micron_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    micron_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    d50_micron: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    d90_micron: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)


class PackagingType(Base, MasterDataMixin):
    __tablename__ = "packaging_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    capacity_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    capacity_uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True
    )
    material: Mapped[str | None] = mapped_column(String(60), nullable=True)   # PP woven, steel, ...
    is_bulk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    capacity_uom: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure")
