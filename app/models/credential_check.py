import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

CHECK_KINDS = {"cr": "Commercial Registration (Wathq)", "mining_license": "Mining licence (MIM)"}
CHECK_RESULTS = {"verified": "Verified", "mismatch": "Name mismatch", "expired": "Expired", "inactive": "Inactive",
                 "not_found": "Not found", "error": "Service error"}


class CredentialCheck(Base, TimestampMixin):
    __tablename__ = "credential_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(60), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    name_on_record: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status_on_record: Mapped[str | None] = mapped_column(String(60), nullable=True)
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    name_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    checked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    company: Mapped["Company"] = relationship("Company")
    checked_by: Mapped["User"] = relationship("User")
