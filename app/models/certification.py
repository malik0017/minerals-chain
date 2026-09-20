"""
app/models/certification.py

Batch A: replaces the old, narrow app/models/certificate.py (lab
Certificate of Analysis) and app/models/passport.py (MineralPassport)
with one generalized master/detail pair. Both old tables modeled
essentially the same shape — a credential issued to a company, with a
number, an issuer, a status, and a validity window — but each hardcoded
its own fields for what should have been the same concept. This is
that concept, done once, properly:

  Certification         — the credential itself: what it is, who
                           issued it, when, and whether it's still
                           valid. One row per issued (or pending, or
                           rejected) credential — a lab Certificate of
                           Analysis and a Mineral Passport are now both
                           just a Certification with a different
                           cert_type.
  CertificationScope     — what the credential actually covers: which
                           product(s) (or the whole company if none),
                           which measured attribute and its valid
                           range, and which geographic region it's
                           valid for. A single Certification can carry
                           multiple scope rows — e.g. one Mineral
                           Passport with an "international_export"
                           category still only needs one scope row
                           today (product + region), but the shape
                           supports a future lab certificate that
                           covers several tested attributes on one
                           product without another migration.

VerificationRequest (app/models/verification.py) is UNCHANGED and
stays separate — it's the workflow object (requested -> scheduled ->
tested -> issued/failed), not the credential. On successful
verification, verification_service.py now calls
certification_service.py to create the resulting Certification,
instead of creating its own narrow Certificate row.

`category` replaces the old rigid PassportScope enum (domestic /
gcc_export / international_export) with a free string, validated at
the schema layer (schemas/certification.py) against the same three
values today — but not locked into a DB enum that would need a
migration the next time a new scope value is needed. Lab certificates
currently don't use `category` at all (left null) — nothing in BRD
calls for classifying lab certs into groups yet.

Expiry status is a computed property, not a stored column — see
MineralPassport's old is_currently_valid docstring reasoning, same
logic applies: a stored "is this expired" flag can silently go stale;
deriving it from expiry_date on read never can.
"""
import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class CertificationType(str, enum.Enum):
    LAB_CERTIFICATE = "lab_certificate"      # was: Certificate (BRD §6.3)
    MINERAL_PASSPORT = "mineral_passport"    # was: MineralPassport (BRD §6.4)
    # Extensible: e.g. "iso_certification" later — the whole point of
    # consolidating was to not need a new table for the next credential type.


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
    # Free-text classification — see module docstring for why this replaced PassportScope.
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # The company this credential is FOR (was seller_company_id on MineralPassport,
    # implicit-via-product on Certificate). Generic name since cert_type may expand
    # beyond seller-only credentials later.
    subject_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    # The lab that issued it — null for admin-issued credentials (e.g. a Mineral Passport).
    issuing_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )
    # Links a lab_certificate back to the workflow that produced it. Null for
    # mineral_passport (passports are requested/reviewed directly, no verification
    # workflow object involved).
    verification_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("verification_requests.id"), nullable=True, unique=True
    )
    issued_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    certificate_number: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # was tested_parameters_notes

    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # null = no expiry (lab certs today)

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

    subject_company: Mapped["Company"] = relationship("Company", foreign_keys=[subject_company_id])
    issuing_company: Mapped["Company"] = relationship("Company", foreign_keys=[issuing_company_id])
    verification_request: Mapped["VerificationRequest"] = relationship(
        "VerificationRequest", foreign_keys=[verification_request_id]
    )
    scopes: Mapped[list["CertificationScope"]] = relationship(
        "CertificationScope", back_populates="certification", cascade="all, delete-orphan"
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
