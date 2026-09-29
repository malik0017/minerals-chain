"""app/schemas/rfq.py"""
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_validator


class RFQRequest(BaseModel):
    mineral_type: str
    specifications_notes: str | None = None
    quantity_value: Decimal
    quantity_unit: str = "MT"
    delivery_location: str
    delivery_timeframe: str
    commercial_terms_notes: str | None = None
    product_master_id: uuid.UUID | None = None
    incoterm_id: uuid.UUID | None = None
    required_by: date | None = None
    payment_terms_days: int | None = None

    @field_validator("product_master_id", "incoterm_id", "required_by", "payment_terms_days", mode="before")
    @classmethod
    def _empty_none(cls, v):
        return None if v in ("", None) else v

    @field_validator("required_by")
    @classmethod
    def _future(cls, v):
        if v is not None and v < date.today():
            raise ValueError("Required-by date can't be in the past.")
        return v

    @field_validator("payment_terms_days")
    @classmethod
    def _terms(cls, v):
        if v is not None and not 0 <= v <= 365:
            raise ValueError("Payment terms must be between 0 and 365 days.")
        return v

    @field_validator("mineral_type", "quantity_unit", "delivery_location", "delivery_timeframe")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field cannot be blank.")
        return v

    @field_validator("quantity_value")
    @classmethod
    def _quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Quantity must be greater than zero.")
        return v
