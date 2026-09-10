"""
app/modules/buyer/rfq/routes.py

BRD §6.5. Every route gated by require_buyer_company — real buyer,
approved company only, no admin bypass (same reasoning as
require_seller_company/require_lab_company).
"""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.permissions import require_buyer_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import quotation_repository, rfq_repository
from app.schemas.rfq import RFQRequest
from app.services.order_service import OrderActionError, accept_quotation
from app.services.rfq_service import RFQActionError, get_owned_rfq, create_rfq

router = APIRouter(prefix="/buyer/rfqs", tags=["buyer-rfq"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="buyer_rfqs_index")
def rfqs_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
):
    rfqs = rfq_repository.list_for_company(db, user.company_id)
    context = build_portal_context(user, UserRole.BUYER, active_path=request.url.path)
    context["rfqs"] = rfqs
    return templates.TemplateResponse(request, "buyer/rfq_index.html", context)


@router.get("/new", name="buyer_rfq_new")
def rfq_new(
    request: Request,
    user: User = Depends(require_buyer_company),
):
    context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/rfqs")
    context.update({"errors": [], "form": {}})
    return templates.TemplateResponse(request, "buyer/rfq_form.html", context)


@router.post("", name="buyer_rfq_create")
def rfq_create(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
    mineral_type: str = Form(...),
    specifications_notes: str = Form(""),
    quantity_value: str = Form(...),
    quantity_unit: str = Form("MT"),
    delivery_location: str = Form(...),
    delivery_timeframe: str = Form(...),
    commercial_terms_notes: str = Form(""),
):
    raw_form = {
        "mineral_type": mineral_type, "specifications_notes": specifications_notes,
        "quantity_value": quantity_value, "quantity_unit": quantity_unit,
        "delivery_location": delivery_location, "delivery_timeframe": delivery_timeframe,
        "commercial_terms_notes": commercial_terms_notes,
    }
    try:
        payload = RFQRequest(
            mineral_type=mineral_type,
            specifications_notes=specifications_notes or None,
            quantity_value=quantity_value,
            quantity_unit=quantity_unit or "MT",
            delivery_location=delivery_location,
            delivery_timeframe=delivery_timeframe,
            commercial_terms_notes=commercial_terms_notes or None,
        )
    except ValidationError as exc:
        errors = [err["msg"] for err in exc.errors()]
        context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/rfqs")
        context.update({"errors": errors, "form": raw_form})
        return templates.TemplateResponse(request, "buyer/rfq_form.html", context, status_code=422)

    rfq = create_rfq(db, user.company, payload)
    return RedirectResponse(url=request.url_for("buyer_rfq_detail", rfq_id=rfq.id), status_code=303)


@router.get("/{rfq_id}", name="buyer_rfq_detail")
def rfq_detail(
    request: Request,
    rfq_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
    error: str | None = None,
):
    try:
        rfq = get_owned_rfq(db, rfq_id, user.company_id)
    except RFQActionError:
        return RedirectResponse(url=request.url_for("buyer_rfqs_index"), status_code=303)

    context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/rfqs")
    context["rfq"] = rfq
    context["quotations"] = quotation_repository.list_for_rfq(db, rfq.id)
    context["error"] = error
    return templates.TemplateResponse(request, "buyer/rfq_detail.html", context)


@router.post("/{rfq_id}/quotations/{quotation_id}/accept", name="buyer_rfq_accept_quotation")
def rfq_accept_quotation(
    request: Request,
    rfq_id: uuid.UUID,
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
):
    try:
        rfq = get_owned_rfq(db, rfq_id, user.company_id)
        quotation = quotation_repository.get_by_id(db, quotation_id)
        if quotation is None:
            raise OrderActionError("Quotation not found.")
        order = accept_quotation(db, rfq, quotation, user.company)
    except (RFQActionError, OrderActionError) as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('buyer_rfq_detail', rfq_id=rfq_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("buyer_order_detail", order_id=order.id), status_code=303)
