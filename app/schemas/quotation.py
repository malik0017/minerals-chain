"""app/schemas/quotation.py"""
from decimal import Decimal

from pydantic import BaseModel, field_validator


class QuotationRequest(BaseModel):
    price_value: Decimal
    price_currency: str = "SAR"
    price_unit: str | None = None
    lead_time_days: int
    terms_notes: str | None = None

    @field_validator("price_value")
    @classmethod
    def _price_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Price must be greater than zero.")
        return v

    @field_validator("lead_time_days")
    @classmethod
    def _lead_time_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Lead time must be at least 1 day.")
        return v

    @field_validator("price_currency")
    @classmethod
    def _currency_not_blank(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Currency cannot be blank.")
        return v
