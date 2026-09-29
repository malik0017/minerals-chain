"""
app/models/ui_translation.py
"""
import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class UITranslation(Base, TimestampMixin):
    __tablename__ = "ui_translations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_text: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    text_ar: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(String(60), nullable=True)  # e.g. "admin", "seller", "status"
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __str__(self) -> str:
        return self.source_text[:60]
