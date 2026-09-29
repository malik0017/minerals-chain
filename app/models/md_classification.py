"""
app/models/md_classification.py
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.md_base import MasterDataMixin


class MineralGroup(Base, MasterDataMixin):
    __tablename__ = "mineral_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mineral_types: Mapped[list["MineralType"]] = relationship("MineralType", back_populates="group", passive_deletes="all")


class MineralType(Base, MasterDataMixin):
    __tablename__ = "mineral_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mineral_groups.id"), nullable=False, index=True
    )
    chemical_formula: Mapped[str | None] = mapped_column(String(40), nullable=True)  # e.g. CaCO3

    group: Mapped["MineralGroup"] = relationship("MineralGroup", back_populates="mineral_types")
    grades: Mapped[list["Grade"]] = relationship("Grade", back_populates="mineral_type", passive_deletes="all")


class Grade(Base, MasterDataMixin):
    __tablename__ = "grades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mineral_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mineral_types.id"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True
    )
    purity_min_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 3), nullable=True)
    quality_level: Mapped[str | None] = mapped_column(String(10), nullable=True)  # A / B / C
    spec_version: Mapped[str] = mapped_column(String(20), nullable=False, default="V1.0")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    mineral_type: Mapped["MineralType"] = relationship("MineralType", back_populates="grades")
    application: Mapped["Application"] = relationship("Application")
