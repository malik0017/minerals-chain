"""app/schemas/certification.py"""
from pydantic import BaseModel, field_validator

# Free-string category, validated here rather than a DB enum — see
# models/certification.py's docstring for why. Same three values the
# old PassportScope enum had; the DB doesn't enforce this list, this
# schema does.
ALLOWED_PASSPORT_CATEGORIES = {"domestic", "gcc_export", "international_export"}


class IssueLabCertificateRequest(BaseModel):
    notes: str

    @field_validator("notes")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tested parameters / results are required to issue a certificate.")
        return v


class RejectCertificationRequest(BaseModel):
    rejection_reason: str

    @field_validator("rejection_reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A rejection reason is required.")
        return v


class PassportRequestCreate(BaseModel):
    category: str

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_PASSPORT_CATEGORIES:
            raise ValueError("Choose a valid trade scope.")
        return v
