"""
app/models/content_page.py
"""
import uuid

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class ContentPage(Base, TimestampMixin):
    __tablename__ = "content_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    title_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body_en: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __str__(self) -> str:
        return f"{self.slug} — {self.title_en}"
