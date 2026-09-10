"""
app/modules/seller/rfq_inbox/routes.py

The seller's look at buyer demand, and (Batch 3) where they respond
with a quotation. Gated by require_seller_company, same as listings
management.
"""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.permissions import require_seller_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import quotation_repository, rfq_repository
from app.schemas.quotation import QuotationRequest
from app.services.quotation_service import QuotationActionError, submit_quotation

router = APIRouter(prefix="/seller/rfq-inbox", tags=["seller-rfq-inbox"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="seller_rfq_inbox_index")
def rfq_inbox_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    rfqs = rfq_repository.list_open(db)
    context = build_portal_context(user, UserRole.SELLER, active_path=request.url.path)
    context["rfqs"] = rfqs
    return templates.TemplateResponse(request, "seller/rfq_inbox_index.html", context)


@router.get("/{rfq_id}", name="seller_rfq_inbox_detail")
def rfq_inbox_detail(
    request: Request,
    rfq_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    error: str | None = None,
):
    rfq = rfq_repository.get_by_id(db, rfq_id)
    if rfq is None:
        return RedirectResponse(url=request.url_for("seller_rfq_inbox_index"), status_code=303)

    my_quotation = quotation_repository.get_by_rfq_and_seller(db, rfq.id, user.company_id)

    context = build_portal_context(user, UserRole.SELLER, active_path="/seller/rfq-inbox")
    context.update({"rfq": rfq, "my_quotation": my_quotation, "error": error})
    return templates.TemplateResponse(request, "seller/rfq_inbox_detail.html", context)


@router.post("/{rfq_id}/quote", name="seller_rfq_submit_quote")
def rfq_submit_quote(
    request: Request,
    rfq_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    price_value: str = Form(...),
    price_currency: str = Form("SAR"),
    price_unit: str = Form(""),
    lead_time_days: str = Form(...),
    terms_notes: str = Form(""),
):
    rfq = rfq_repository.get_by_id(db, rfq_id)
    if rfq is None:
        return RedirectResponse(url=request.url_for("seller_rfq_inbox_index"), status_code=303)

    try:
        payload = QuotationRequest(
            price_value=price_value,
            price_currency=price_currency or "SAR",
            price_unit=price_unit or None,
            lead_time_days=lead_time_days,
            terms_notes=terms_notes or None,
        )
        submit_quotation(db, rfq, user.company, payload)
    except (ValidationError, QuotationActionError) as exc:
        db.rollback()
        msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(
            url=f"{request.url_for('seller_rfq_inbox_detail', rfq_id=rfq_id)}?error={msg}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("seller_rfq_inbox_detail", rfq_id=rfq_id), status_code=303)
