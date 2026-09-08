"""app/schemas/product.py"""
from decimal import Decimal

from pydantic import BaseModel, field_validator


class ProductRequest(BaseModel):
    mineral_type: str
    grade: str | None = None
    specifications_notes: str | None = None

    quantity_value: Decimal
    quantity_unit: str = "MT"

    price_value: Decimal | None = None
    price_currency: str = "SAR"
    price_unit: str | None = None

    packaging: str | None = None
    trade_terms: str | None = None

    @field_validator("mineral_type", "quantity_unit")
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

    @field_validator("price_value")
    @classmethod
    def _price_non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("Price cannot be negative.")
        return v

    @field_validator("price_currency")
    @classmethod
    def _currency_code(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 3:
            raise ValueError("Currency must be a 3-letter code (e.g. SAR).")
        return v
