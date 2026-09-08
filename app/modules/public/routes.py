"""
app/modules/public/routes.py

BRD §6.4: "The system shall support independent verification of a
passport's authenticity (e.g., via a public reference lookup)." No
login required — this is meant to be checked by a buyer, customs
official, or anyone else holding a passport number, not just
platform members. Deliberately minimal information disclosed: mineral
type, scope, validity window, and issuing (seller) company name —
nothing about the buyer side of any transaction, since there isn't
one to disclose yet, and nothing internal (no user emails, no
rejection reasons for other passports, etc).
"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database.base import get_db
from app.repositories import passport_repository

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/passports/verify", name="public_passport_verify")
def passport_verify(
    request: Request,
    db: Session = Depends(get_db),
    number: str | None = None,
):
    passport = None
    searched = number is not None and number.strip() != ""
    if searched:
        passport = passport_repository.get_by_number(db, number.strip().upper())

    return templates.TemplateResponse(
        request,
        "public/passport_lookup.html",
        {"number": number or "", "passport": passport, "searched": searched},
    )
