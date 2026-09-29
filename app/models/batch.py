"""
app/models/batch.py
"""
import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class BatchStage(str, enum.Enum):
    EXTRACTION = "extraction"
    PROCESSING = "processing"
    FINISHED = "finished"


class BatchStatus(str, enum.Enum):
    QUARANTINE = "quarantine"   # default: nothing may be sold from it yet
    RELEASED = "released"
    REJECTED = "rejected"
    BLOCKED = "blocked"         # admin hold (e.g. dispute, recall)
    CONSUMED = "consumed"       # fully sold / processed into a child batch


class QCStatus(str, enum.Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


def _enum(enum_cls, name):
    return SAEnum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class Batch(Base, TimestampMixin):
    __tablename__ = "batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)  # LOT-2026-00125
    lot_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_batch_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)  # mine's own reference

    product_master_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_masters.id"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )
    listing_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True, index=True
    )
    mine_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mine_sources.id"), nullable=True
    )
    parent_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True
    )
    stage: Mapped[BatchStage] = mapped_column(_enum(BatchStage, "batch_stage"), nullable=False, default=BatchStage.FINISHED)

    production_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True)
    bin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouse_bins.id"), nullable=True)

    status: Mapped[BatchStatus] = mapped_column(_enum(BatchStatus, "batch_status"), nullable=False, default=BatchStatus.QUARANTINE)
    qc_status: Mapped[QCStatus] = mapped_column(_enum(QCStatus, "qc_status"), nullable=False, default=QCStatus.PENDING)
    qc_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    product_master: Mapped["ProductMaster"] = relationship("ProductMaster")
    company: Mapped["Company"] = relationship("Company")
    listing_product: Mapped["Product"] = relationship("Product")
    mine_source: Mapped["MineSource"] = relationship("MineSource")
    parent_batch: Mapped["Batch"] = relationship("Batch", remote_side=[id])
    uom: Mapped["UnitOfMeasure"] = relationship("UnitOfMeasure")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    bin: Mapped["WarehouseBin"] = relationship("WarehouseBin")
    results: Mapped[list["BatchQualityResult"]] = relationship(
        "BatchQualityResult", back_populates="batch", cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        return self.batch_number


class BatchQualityResult(Base, TimestampMixin):
    __tablename__ = "batch_quality_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False, index=True)
    parameter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_parameters.id"), nullable=False
    )
    measured_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    spec_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    spec_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    uom_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    test_method_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_methods.id"), nullable=True
    )
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # null = no spec to judge against
    certification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certifications.id"), nullable=True
    )
    tested_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    batch: Mapped["Batch"] = relationship("Batch", back_populates="results")
    parameter: Mapped["QualityParameter"] = relationship("QualityParameter")
    test_method: Mapped["TestMethod"] = relationship("TestMethod")
