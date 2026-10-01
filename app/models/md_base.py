"""
app/models/md_base.py
"""
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import TimestampMixin


class MasterDataMixin(TimestampMixin):
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(150), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def display_name(self, lang: str = "en") -> str:
        if lang == "ar" and self.name_ar:
            return self.name_ar
        return self.name_en

    def __str__(self) -> str: 
        return f"{self.code} — {self.name_en}"
