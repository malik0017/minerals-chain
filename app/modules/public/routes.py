"""
app/modules/public/routes.py
"""
from fastapi import APIRouter, Request
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database.base import get_db
from app.models.certification import CertificationType
from app.repositories import certification_repository

router = APIRouter(tags=["public"])
from app.core.templates import templates


@router.get("/passports/verify", name="public_passport_verify")
def passport_verify(
    request: Request,
    db: Session = Depends(get_db),
    number: str | None = None,
):
    passport = None
    searched = number is not None and number.strip() != ""
    if searched:
        candidate = certification_repository.get_by_number(db, number.strip().upper())
        # Only ever resolve to an actual Mineral Passport here — a lab
        # certificate number should never validate on this lookup.
        if candidate is not None and candidate.cert_type == CertificationType.MINERAL_PASSPORT:
            passport = candidate

    return templates.TemplateResponse(
        request,
        "public/passport_lookup.html",
        {"number": number or "", "passport": passport, "searched": searched},
    )
