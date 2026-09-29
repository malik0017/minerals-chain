"""
app/models/user.py
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin

class UserRole(str, enum.Enum):
    SELLER = "seller"
    BUYER = "buyer"
    LAB = "lab"
    ADMIN = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True
    )

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    preferred_language: Mapped[str] = mapped_column(String(2), nullable=False, default="en")
    avatar_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")
    admin_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    privacy_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    privacy_consent_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Relationships ---
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="users",
        foreign_keys=[company_id],
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} ({self.role.value})>"
