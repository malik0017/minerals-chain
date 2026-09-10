"""app/schemas/two_factor.py"""
from pydantic import BaseModel, field_validator


class TotpConfirmRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def _six_digits(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("Enter the 6-digit code from your authenticator app.")
        return v


class TotpDisableRequest(BaseModel):
    current_password: str
    code: str

    @field_validator("code")
    @classmethod
    def _six_digits(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("Enter the 6-digit code from your authenticator app.")
        return v
