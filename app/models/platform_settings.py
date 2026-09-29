"""
app/models/platform_settings.py
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PlatformSettings(Base):
    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    registration_enabled_seller: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    registration_enabled_buyer: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    registration_enabled_lab: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_email_otp: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlatformSettings seller={self.registration_enabled_seller} buyer={self.registration_enabled_buyer} lab={self.registration_enabled_lab} otp={self.require_email_otp}>"
