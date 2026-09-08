"""
app/models/passport.py

BRD §6.4 (Mineral Passport):
  - seller requests a formal passport for a VERIFIED product,
    selecting trade scope: domestic, GCC export, international export
  - passport requests require admin review and approval before issuance
  - an issued passport has a defined validity period, after which
    renewal is required
  - the system supports independent verification of a passport's
    authenticity via a public reference lookup

Validity period assumption: 12 months from approval date. BRD doesn't
specify an exact duration, and there's no admin-configurable policy
UI for it yet — a fixed 12-month window is a reasonable default that's
easy to find and change in one place (passport_service.py) once a
real policy exists. Not something to build a settings screen for on
a guess.

Requesting again after a REJECTED or EXPIRED passport is just a new
row — no special "resubmit" flow needed, unlike VerificationRequest
(which locks the underlying Product while active). A passport request
doesn't lock anything on the product itself.
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class PassportScope(str, enum.Enum):
    DOMESTIC = "domestic"
    GCC_EXPORT = "gcc_export"
    INTERNATIONAL_EXPORT = "international_export"


class PassportStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MineralPassport(Base, TimestampMixin):
    __tablename__ = "mineral_passports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    seller_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    scope: Mapped[PassportScope] = mapped_column(
        SAEnum(PassportScope, name="passport_scope", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    status: Mapped[PassportStatus] = mapped_column(
        SAEnum(PassportStatus, name="passport_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=PassportStatus.PENDING,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set only on approval — NULL until then.
    passport_number: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    seller_company: Mapped["Company"] = relationship("Company", foreign_keys=[seller_company_id])

    @property
    def is_currently_valid(self) -> bool:
        """Approved AND within its validity window. Not a DB column —
        computed from status + valid_until so there's never a stale
        'expired but still marked approved' row to reconcile."""
        if self.status != PassportStatus.APPROVED or self.valid_until is None:
            return False
        return date.today() <= self.valid_until

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MineralPassport {self.passport_number or '(pending)'} — product {self.product_id}>"
