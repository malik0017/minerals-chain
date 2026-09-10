"""
app/models/certificate.py
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
