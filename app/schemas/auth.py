"""
app/schemas/auth.py
"""

from typing import Literal
from pydantic import BaseModel, EmailStr, field_validator, model_validator

RegisterableRole = Literal["seller", "buyer", "lab"]


class RegisterRequest(BaseModel):
    role: RegisterableRole

    # --- Company fields ---
    company_name: str
    cr_number: str
    # Batch B: mandatory for every role now, not just seller/lab — see
    # models/company.py's docstring on this field for why.
    license_or_accreditation_number: str
    # Batch B: combined "+966 501234567" — the route builds this from
    # separate country-code + digits-only form fields before validation
    # here reaches it; see modules/auth/routes.py.
    contact_phone: str

    # --- User (the person registering) fields ---
    full_name: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("company_name", "cr_number", "full_name", "license_or_accreditation_number", "contact_phone")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field cannot be blank.")
        return v

    @field_validator("password")
    @classmethod
    def _password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v

    @model_validator(mode="after")
    def _passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
