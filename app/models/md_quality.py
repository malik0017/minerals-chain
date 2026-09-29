"""
app/models/md_quality.py
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.models.md_base import MasterDataMixin


class TestMethod(Base, MasterDataMixin):
    __tablename__ = "test_methods"
    __test__ = False  

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    standard_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)   # e.g. "ASTM C25"
    default_fee_sar: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    turnaround_days: Mapped[int | None] = mapped_column(Integer, nullable=True)


class QualityParameter(Base, MasterDataMixin):
    __tablename__ = "quality_parameters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parameter_type: Mapped[str] = mapped_column(String(20), nullable=False, default="chemical")
    symbol: Mapped[str | None] = mapped_column(String(30), nullable=True)            # display e.g. "SiO₂"
    default_uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True
    )
    default_test_method_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_methods.id"), nullable=True
    )
    decimal_places: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    default_uom: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure")
    default_test_method: Mapped["TestMethod"] = relationship("TestMethod")


class QualitySpecification(Base, TimestampMixin):
    __tablename__ = "quality_specifications"
    __table_args__ = (
        CheckConstraint(
            "(grade_id IS NOT NULL) <> (product_master_id IS NOT NULL)",
            name="ck_quality_spec_grade_xor_product",
        ),
        CheckConstraint(
            "min_value IS NULL OR max_value IS NULL OR min_value <= max_value",
            name="ck_quality_spec_min_le_max",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grades.id"), nullable=True, index=True
    )
    product_master_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_masters.id"), nullable=True, index=True
    )
    parameter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_parameters.id"), nullable=False
    )
    min_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True
    )
    test_method_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_methods.id"), nullable=True
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    spec_version: Mapped[str] = mapped_column(String(20), nullable=False, default="V1.0")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    grade: Mapped["Grade"] = relationship("Grade")
    product_master: Mapped["ProductMaster"] = relationship("ProductMaster")
    parameter: Mapped["QualityParameter"] = relationship("QualityParameter")
    uom: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure")
    test_method: Mapped["TestMethod"] = relationship("TestMethod")

    def range_label(self) -> str:
        """PDF §10 style: "≥ 95 %", "≤ 2 %", "0–5 mm". A 0 lower bound on a
        max-only limit (e.g. SiO2 0–2 %) reads as "≤ 2"."""
        def fmt(v) -> str:
            return f"{Decimal(v).normalize():f}"
        unit = (self.uom.symbol or self.uom.code) if self.uom else ""
        lo, hi = self.min_value, self.max_value
        if lo is not None and hi is not None and lo != 0:
            return f"{fmt(lo)}–{fmt(hi)} {unit}".strip()
        if hi is not None:
            return f"≤ {fmt(hi)} {unit}".strip()
        if lo is not None:
            return f"≥ {fmt(lo)} {unit}".strip()
        return "—"

    def __str__(self) -> str:
        owner = self.grade.code if self.grade else (self.product_master.code if self.product_master else "?")
        return f"{owner}: {self.parameter.code if self.parameter else '?'} {self.range_label()}"
