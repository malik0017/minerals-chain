"""app/schemas/rfq.py"""
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
