"""
app/models/user.py

"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
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

    # Mirrors company approval for seller/buyer/lab users; admins are active on creation.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # BRD §6.10 Localization — per-user language preference, drives dir="rtl" in base.html.
    preferred_language: Mapped[str] = mapped_column(String(2), nullable=False, default="en")

    # Batch 8: just the filename (e.g. "3f2a...-c9.png"), not a full path —
    # the upload route (services/avatar_service.py) controls where files
    # actually live on disk (app/static/uploads/avatars/). NULL means "no
    # custom avatar", and every template falls back to a default
    # placeholder image rather than treating NULL as an error.
    avatar_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="users",
        foreign_keys=[company_id],
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} ({self.role.value})>"
