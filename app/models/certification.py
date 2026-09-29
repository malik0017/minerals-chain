"""
app/models/certification.py
"""
import enum
import uuid
from datetime import date, datetime, timezone

from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class CertificationType(str, enum.Enum):
    LAB_CERTIFICATE = "lab_certificate"      # was: Certificate 
    MINERAL_PASSPORT = "mineral_passport"    # was: MineralPassport 


class CertificationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Certification(Base, TimestampMixin):
    __tablename__ = "certifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    cert_type: Mapped[CertificationType] = mapped_column(
        SAEnum(CertificationType, name="certification_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    issuing_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    verification_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("verification_requests.id"), nullable=True, unique=True
    )
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    certificate_number: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  

    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)  

    status: Mapped[CertificationStatus] = mapped_column(
        SAEnum(CertificationStatus, name="certification_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=CertificationStatus.PENDING,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    analyst_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sample_collected_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    all_parameters_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_off_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    fee_sar: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    source_certification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certifications.id"), nullable=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("batches.id"), nullable=True)
    # --- Batch M3: passport renewal (BRD §6.4) — the passport this one renews
    renewal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certifications.id"), nullable=True
    )
    is_expedited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # premium tier (BRD §6.11)

    subject_company: Mapped["Company"] = relationship("Company", foreign_keys=[subject_company_id])
    issuing_company: Mapped["Company"] = relationship("Company", foreign_keys=[issuing_company_id])
    verification_request: Mapped["VerificationRequest"] = relationship(
        "VerificationRequest", foreign_keys=[verification_request_id]
    )
    scopes: Mapped[list["CertificationScope"]] = relationship(
        "CertificationScope", back_populates="certification", cascade="all, delete-orphan"
    )
    results: Mapped[list["CertificationResult"]] = relationship(
        "CertificationResult", back_populates="certification", cascade="all, delete-orphan"
    )

    @property
    def is_currently_valid(self) -> bool:
        if self.status != CertificationStatus.APPROVED:
            return False
        if self.expiry_date is None:
            return True  # no expiry set — treated as valid indefinitely (today's lab certs)
        return date.today() <= self.expiry_date

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Certification {self.certificate_number or '(pending)'} ({self.cert_type.value})>"


class CertificationScope(Base, TimestampMixin):
    """What a Certification actually covers. See module docstring."""
    __tablename__ = "certification_scopes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certifications.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )  # null = applies company-wide, not to one specific listing

    attribute_name: Mapped[str | None] = mapped_column(String(80), nullable=True)   # e.g. "purity"
    attribute_min: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    attribute_max: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)

    geo_region: Mapped[str | None] = mapped_column(String(80), nullable=True)  # e.g. "GCC", "Saudi Arabia"

    certification: Mapped["Certification"] = relationship("Certification", back_populates="scopes")
    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CertificationScope for certification {self.certification_id}>"


class CertificationResult(Base, TimestampMixin):

    __tablename__ = "certification_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    certification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certifications.id"), nullable=False, index=True
    )
    parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_parameters.id"), nullable=True
    )
    parameter: Mapped[str] = mapped_column(String(80), nullable=False)
    required_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    required_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    measured_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    test_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)

    certification: Mapped["Certification"] = relationship("Certification", back_populates="results")
