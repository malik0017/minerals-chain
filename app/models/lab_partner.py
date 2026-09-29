"""
app/models/lab_partner.py
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class LabPartnerTerms(Base, TimestampMixin):
    __tablename__ = "lab_partner_terms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lab_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, unique=True)
    accreditation_body: Mapped[str | None] = mapped_column(String(120), nullable=True)  # e.g. SAC, ISO/IEC 17025
    accreditation_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    accreditation_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    accreditation_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    fee_sar: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    turnaround_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_accepting_requests: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lab_company: Mapped["Company"] = relationship("Company")

    @property
    def accreditation_current(self) -> bool:
        return self.accreditation_valid_until is None or self.accreditation_valid_until >= date.today()
