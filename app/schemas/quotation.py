"""app/schemas/quotation.py"""
import uuid
from decimal import Decimal

from pydantic import BaseModel, field_validator


class QuotationRequest(BaseModel):
    price_value: Decimal
    price_currency: str = "SAR"
    price_unit: str | None = None
    lead_time_days: int
    terms_notes: str | None = None
    product_id: uuid.UUID | None = None
    incoterm_id: uuid.UUID | None = None
    payment_terms_days: int | None = None
    validity_days: int | None = None

    @field_validator("product_id", "incoterm_id", "payment_terms_days", "validity_days", mode="before")
    @classmethod
    def _empty_none(cls, v):
        return None if v in ("", None) else v

    @field_validator("validity_days")
    @classmethod
    def _validity(cls, v):
        if v is not None and not 1 <= v <= 180:
            raise ValueError("Validity must be between 1 and 180 days.")
        return v

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
