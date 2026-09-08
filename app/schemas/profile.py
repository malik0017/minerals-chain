"""app/schemas/profile.py"""
from pydantic import BaseModel, field_validator, model_validator


class ProfileUpdateRequest(BaseModel):
    full_name: str

    @field_validator("full_name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be blank.")
        return v


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters.")
        return v

    @model_validator(mode="after")
    def _passwords_match(self) -> "PasswordChangeRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("New passwords do not match.")
        return self
