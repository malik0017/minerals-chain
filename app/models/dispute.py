"""
app/models/dispute.py
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    AWAITING_INFO = "awaiting_info"
    RESOLVED = "resolved"
    WITHDRAWN = "withdrawn"


class DisputeRuling(str, enum.Enum):
    BUYER = "buyer"      
    SELLER = "seller"    

def _enum(cls, name):
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Dispute(Base, TimestampMixin):
    __tablename__ = "disputes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True)
    raised_by_party: Mapped[str] = mapped_column(String(10), nullable=False)  # buyer | seller
    raised_by_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    raised_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    # quality | quantity | delivery_delay | damaged | documentation | pricing | other
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    desired_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DisputeStatus] = mapped_column(_enum(DisputeStatus, "dispute_status"), nullable=False,
                                                  default=DisputeStatus.OPEN)
    order_status_before: Mapped[str] = mapped_column(String(30), nullable=False)
    assigned_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    ruling: Mapped[DisputeRuling | None] = mapped_column(_enum(DisputeRuling, "dispute_ruling"), nullable=True)
    decision_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order: Mapped["Order"] = relationship("Order")
    raised_by_company: Mapped["Company"] = relationship("Company")
    raised_by_user: Mapped["User"] = relationship("User", foreign_keys=[raised_by_user_id])
    assigned_admin: Mapped["User"] = relationship("User", foreign_keys=[assigned_admin_id])
    decided_by: Mapped["User"] = relationship("User", foreign_keys=[decided_by_user_id])
    messages: Mapped[list["DisputeMessage"]] = relationship(
        "DisputeMessage", back_populates="dispute", order_by="DisputeMessage.created_at")
    corrections: Mapped[list["DisputeCorrection"]] = relationship(
        "DisputeCorrection", back_populates="dispute", order_by="DisputeCorrection.corrected_at")

    @property
    def is_decided(self) -> bool:
        return self.decided_at is not None

    @property
    def is_active(self) -> bool:
        return self.status in (DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW, DisputeStatus.AWAITING_INFO)


class DisputeMessage(Base, TimestampMixin):
    __tablename__ = "dispute_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispute_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("disputes.id"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    author_party: Mapped[str] = mapped_column(String(10), nullable=False)  # buyer | seller | admin
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attachment_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="messages")
    author: Mapped["User"] = relationship("User")


class DisputeCorrection(Base):
    __tablename__ = "dispute_corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispute_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("disputes.id"), nullable=False, index=True)
    previous_ruling: Mapped[str | None] = mapped_column(String(10), nullable=True)
    new_ruling: Mapped[str | None] = mapped_column(String(10), nullable=True)
    previous_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    dispute: Mapped["Dispute"] = relationship("Dispute", back_populates="corrections")
    corrected_by: Mapped["User"] = relationship("User")
