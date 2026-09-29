"""
app/modules/buyer/rfq/routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.permissions import require_buyer_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from urllib.parse import quote

from starlette.datastructures import FormData

from app.core.forms import form_data
from app.repositories import product_repository, quotation_repository, rfq_repository
from app.services import quotation_service, rfq_service, spec_service
from app.schemas.rfq import RFQRequest
from app.services.order_service import OrderActionError, accept_quotation
from app.services.rfq_service import RFQActionError, get_owned_rfq, create_rfq

router = APIRouter(prefix="/buyer/rfqs", tags=["buyer-rfq"])
from app.core.templates import templates


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


def _form_options(db: Session) -> dict:
    from app.modules.shared.catalog_routes import incoterm_choices, product_choices
    return {"catalog_products": product_choices(db), "incoterms": incoterm_choices(db)}


@router.get("/new", name="buyer_rfq_new")
def rfq_new(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
    product_id: str = "",
):
    form, rows = {}, []
    if product_id:
        try:
            product = product_repository.get_verified_by_id(db, uuid.UUID(product_id))
        except ValueError:
            product = None
        if product is not None:
            form = {"mineral_type": f"{product.mineral_type}{' ' + product.grade if product.grade else ''}",
                    "quantity_unit": product.quantity_unit,
                    "product_master_id": str(product.product_master_id or "")}
            rows = spec_service.product_rows(db, product)
    context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/rfqs")
    context.update({"errors": [], "form": form, "spec_rows": rows, **_form_options(db)})
    return templates.TemplateResponse(request, "buyer/rfq_form.html", context)


@router.post("", name="buyer_rfq_create")
def rfq_create(
    request: Request,
    form: FormData = Depends(form_data),
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
):
    keys = ("mineral_type", "specifications_notes", "quantity_value", "quantity_unit", "delivery_location",
            "delivery_timeframe", "commercial_terms_notes", "product_master_id", "incoterm_id", "required_by",
            "payment_terms_days")
    raw_form = {k: (form.get(k) or "").strip() for k in keys}
    errors, rows = [], []
    try:
        rows = spec_service.parse_rows(form, "spec")
    except spec_service.SpecError as exc:
        errors.append(f"Specification: {exc}")
    payload = None
    try:
        payload = RFQRequest(
            mineral_type=raw_form["mineral_type"],
            specifications_notes=raw_form["specifications_notes"] or None,
            quantity_value=raw_form["quantity_value"] or "0",
            quantity_unit=raw_form["quantity_unit"] or "MT",
            delivery_location=raw_form["delivery_location"],
            delivery_timeframe=raw_form["delivery_timeframe"] or (f"By {raw_form['required_by']}" if raw_form["required_by"] else ""),
            commercial_terms_notes=raw_form["commercial_terms_notes"] or None,
            product_master_id=raw_form["product_master_id"], incoterm_id=raw_form["incoterm_id"],
            required_by=raw_form["required_by"], payment_terms_days=raw_form["payment_terms_days"],
        )
    except ValidationError as exc:
        errors += [f"{err['loc'][-1].replace('_', ' ').capitalize()}: {err['msg']}" if err.get("loc") else err["msg"]
                   for err in exc.errors()]
    if not errors:
        try:
            rfq = create_rfq(db, user.company, payload, created_by=user, spec_rows=rows)
        except RFQActionError as exc:  # Batch K: e.g. subscription RFQ limit reached
            db.rollback()
            errors = [str(exc)]
    if errors:
        context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/rfqs")
        context.update({"errors": errors, "form": raw_form, "spec_rows": rows, **_form_options(db)})
        return templates.TemplateResponse(request, "buyer/rfq_form.html", context, status_code=422)
    return RedirectResponse(url=request.url_for("buyer_rfq_detail", rfq_id=rfq.id), status_code=303)


@router.get("/{rfq_id}", name="buyer_rfq_detail")
def rfq_detail(
    request: Request,
    rfq_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
    error: str | None = None,
    msg: str | None = None,
    sort: str = "price",
):
    try:
        rfq = get_owned_rfq(db, rfq_id, user.company_id)
    except RFQActionError:
        return RedirectResponse(url=request.url_for("buyer_rfqs_index"), status_code=303)

    quotation_service.expire_stale(db)
    context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/rfqs")
    context.update({"rfq": rfq, "rows": quotation_service.comparison(db, rfq, sort), "sort": sort,
                    "error": error, "msg": msg, "spec_rows": rfq_service.spec_rows(rfq),
                    "accepting": rfq_service.accepting_quotes(rfq)})
    return templates.TemplateResponse(request, "buyer/rfq_detail.html", context)


@router.post("/{rfq_id}/cancel", name="buyer_rfq_cancel")
def rfq_cancel(request: Request, rfq_id: uuid.UUID, reason: str = Form(""), db: Session = Depends(get_db),
               user: User = Depends(require_buyer_company)):
    url = str(request.url_for("buyer_rfq_detail", rfq_id=rfq_id))
    try:
        rfq = get_owned_rfq(db, rfq_id, user.company_id)
        rfq_service.cancel_rfq(db, rfq, user, reason)
    except RFQActionError as exc:
        db.rollback()
        return RedirectResponse(url=f"{url}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"{url}?msg={quote('RFQ cancelled. Sellers who quoted were notified.')}", status_code=303)


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
            url=f"{request.url_for('buyer_rfq_detail', rfq_id=rfq_id)}?error={quote(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("buyer_order_detail", order_id=order.id), status_code=303)
