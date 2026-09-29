"""
app/models/data_request.py
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class DataRequestType(str, enum.Enum):
    ACCESS = "access"
    CORRECTION = "correction"
    DELETION = "deletion"
    RESTRICTION = "restriction"
    OBJECTION = "objection"


class DataRequestStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"


class DataRequest(Base, TimestampMixin):
    __tablename__ = "data_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    request_type: Mapped[DataRequestType] = mapped_column(
        SAEnum(DataRequestType, name="data_request_type", values_callable=lambda e: [m.value for m in e]), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DataRequestStatus] = mapped_column(
        SAEnum(DataRequestStatus, name="data_request_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=DataRequestStatus.OPEN)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])
    handled_by: Mapped["User"] = relationship("User", foreign_keys=[handled_by_user_id])
