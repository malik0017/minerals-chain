"""
app/models/verification.py

BRD §6.3 (Lab Verification):
  - seller requests verification of a listed product from an
    accredited lab registered on the platform
  - defined lifecycle: requested, sample scheduled, testing in
    progress, completed, failed
  - "Upon failed verification, the lab shall document a rejection
    reason, and the associated product shall return to a non-visible
    state"

Simplification for this batch: the UI only exercises REQUESTED ->
COMPLETED or REQUESTED -> FAILED directly (see verification_service.py)
— SAMPLE_SCHEDULED and TESTING_IN_PROGRESS exist in the enum because
BRD names them as part of the lifecycle, but building granular
staged-progress UI for them (with no real sample-logistics feature
behind it yet) would be UI for its own sake. A lab can move a request
through those intermediate states later without a schema change once
there's an actual reason to (e.g. showing the seller "your sample is
being tested" rather than just "requested").

The seller chooses a specific lab at request time (lab_company_id is
NOT NULL from creation) rather than an open/unclaimed marketplace
model — matches "request verification ... from an accredited
laboratory" reading naturally as the seller picking one.
"""
import enum
import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class VerificationStatus(str, enum.Enum):
    REQUESTED = "requested"
    SAMPLE_SCHEDULED = "sample_scheduled"
    TESTING_IN_PROGRESS = "testing_in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationRequest(Base, TimestampMixin):
    __tablename__ = "verification_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    lab_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )

    status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verification_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=VerificationStatus.REQUESTED,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    lab_company: Mapped["Company"] = relationship("Company", foreign_keys=[lab_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VerificationRequest product={self.product_id} lab={self.lab_company_id} ({self.status.value})>"
