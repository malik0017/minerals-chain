"""
app/models/certificate.py

BRD §6.3: "Upon successful verification, the lab shall issue a
Certificate of Analysis documenting tested parameters against
required thresholds." §6.6/§10.6: retained as a permanent, auditable
record.

`product_id` and `lab_company_id` are denormalized here (also
reachable via verification_request) on purpose — a certificate is a
permanent legal-ish document; querying it shouldn't depend on
traversing through a request row that, in principle, is a workflow
object and not the record of truth. `tested_parameters_notes` mirrors
Product.specifications_notes' free-text approach for the same reason
(see product.py's docstring) — a structured schema of expected vs.
measured values per mineral type is real future work, not speculative
scope for this batch.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    verification_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("verification_requests.id"), nullable=False, unique=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    lab_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    issued_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    certificate_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    tested_parameters_notes: Mapped[str] = mapped_column(Text, nullable=False)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id])
    lab_company: Mapped["Company"] = relationship("Company", foreign_keys=[lab_company_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Certificate {self.certificate_number} for product {self.product_id}>"
