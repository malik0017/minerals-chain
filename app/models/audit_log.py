"""
app/models/audit_log.py
""" 

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Task #7: the audit-log viewer needs the actor's name/email on every
    # row — this is a read-only relationship (no back_populates on User,
    # so a user's own model/other pages are untouched by this addition).
    actor = relationship("User", foreign_keys=[actor_user_id], viewonly=True)

    action: Mapped[str] = mapped_column(String(50), nullable=False)       # e.g. "company_approved"
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "company"
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # e.g. rejection reason

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog {self.action} on {self.target_type}:{self.target_id}>"
