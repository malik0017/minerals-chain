"""
app/models/platform_settings.py

Task #4: a single-row settings table the admin can toggle at runtime —
whether each role can self-register right now, and whether registration
requires proving control of the email address via OTP (a dev-mode
convenience toggle; leaving this on is the safe default for production).

Deliberately a single row (id is always 1) rather than a key/value table:
there are only a handful of booleans, they're all read on every page load
that touches registration, and a fixed-shape row is simpler to work with
from both Python and the admin template than a generic settings store.
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

    # When False, /register no longer requires the email-OTP step before
    # submitting — a dev/staging convenience. Defaults True (today's
    # existing, safe behavior) so nothing changes until an admin opts in.
    require_email_otp: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlatformSettings seller={self.registration_enabled_seller} buyer={self.registration_enabled_buyer} lab={self.registration_enabled_lab} otp={self.require_email_otp}>"
