"""app/schemas/verification.py"""
import uuid

from pydantic import BaseModel, field_validator


class VerificationRequestCreate(BaseModel):
    lab_company_id: uuid.UUID


class IssueCertificateRequest(BaseModel):
    tested_parameters_notes: str

    @field_validator("tested_parameters_notes")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tested parameters / results are required to issue a certificate.")
        return v


class RejectVerificationRequest(BaseModel):
    rejection_reason: str

    @field_validator("rejection_reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A rejection reason is required.")
        return v
