"""
app/modules/seller/rfq_inbox/routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.permissions import require_seller_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from urllib.parse import quote

from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.system_settings import get_setting
from app.models.product import ProductStatus
from app.repositories import product_repository, quotation_repository, rfq_repository
from app.services import quotation_service, rfq_service, spec_service
from app.schemas.quotation import QuotationRequest
from app.services.quotation_service import QuotationActionError, submit_quotation

router = APIRouter(prefix="/seller/rfq-inbox", tags=["seller-rfq-inbox"])
from app.core.templates import templates


@router.get("", name="seller_rfq_inbox_index")
def rfq_inbox_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    rfqs = [r for r in rfq_repository.list_open(db) if rfq_service.accepting_quotes(r)]
    context = build_portal_context(user, UserRole.SELLER, active_path=request.url.path)
    context["rfqs"] = rfqs
    mine = {q.rfq_id: q for q in quotation_repository.list_for_seller_company(db, user.company_id)}
    context["quoted"] = mine
    from datetime import datetime, timezone
    context["now_utc"] = datetime.now(timezone.utc)
    return templates.TemplateResponse(request, "seller/rfq_inbox_index.html", context)


@router.get("/{rfq_id}", name="seller_rfq_inbox_detail")
def rfq_inbox_detail(
    request: Request,
    rfq_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    error: str | None = None,
    msg: str | None = None,
):
    rfq = rfq_repository.get_by_id(db, rfq_id)
    if rfq is None:
        return RedirectResponse(url=request.url_for("seller_rfq_inbox_index"), status_code=303)

    quotation_service.expire_stale(db)
    my_quotation = quotation_repository.get_by_rfq_and_seller(db, rfq.id, user.company_id)
    required = rfq_service.spec_rows(rfq)
    listings = [(p, spec_service.match_score(required, spec_service.product_rows(db, p)))
                for p in product_repository.list_for_company(db, user.company_id) if p.status == ProductStatus.VERIFIED]
    listings.sort(key=lambda x: -(x[1] if x[1] is not None else -1))
    from app.modules.shared.catalog_routes import incoterm_choices
    context = build_portal_context(user, UserRole.SELLER, active_path="/seller/rfq-inbox")
    context.update({"rfq": rfq, "my_quotation": my_quotation, "error": error, "msg": msg, "spec_rows": required,
                    "listings": listings, "incoterms": incoterm_choices(db),
                    "accepting": rfq_service.accepting_quotes(rfq),
                    "default_validity": get_setting(db, "quotation_validity_days")})
    return templates.TemplateResponse(request, "seller/rfq_inbox_detail.html", context)


def _payload(form) -> QuotationRequest:
    return QuotationRequest(
        price_value=form.get("price_value") or "0", price_currency=form.get("price_currency") or "SAR",
        price_unit=form.get("price_unit") or None, lead_time_days=form.get("lead_time_days") or "0",
        terms_notes=form.get("terms_notes") or None, product_id=form.get("product_id"),
        incoterm_id=form.get("incoterm_id"), payment_terms_days=form.get("payment_terms_days"),
        validity_days=form.get("validity_days"))


def _back(request: Request, rfq_id, *, error: str | None = None, msg: str | None = None):
    url = str(request.url_for("seller_rfq_inbox_detail", rfq_id=rfq_id))
    if error:
        url += "?error=" + quote(error)
    elif msg:
        url += "?msg=" + quote(msg)
    return RedirectResponse(url=url, status_code=303)


@router.post("/{rfq_id}/quote", name="seller_rfq_submit_quote")
def rfq_submit_quote(request: Request, rfq_id: uuid.UUID, form: FormData = Depends(form_data),
                     db: Session = Depends(get_db), user: User = Depends(require_seller_company)):
    rfq = rfq_repository.get_by_id(db, rfq_id)
    if rfq is None:
        return RedirectResponse(url=request.url_for("seller_rfq_inbox_index"), status_code=303)
    try:
        submit_quotation(db, rfq, user.company, _payload(form), submitted_by=user)
    except (ValidationError, QuotationActionError) as exc:
        db.rollback()
        return _back(request, rfq_id, error=exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc))
    return _back(request, rfq_id, msg="Quotation submitted.")


@router.post("/{rfq_id}/revise", name="seller_rfq_revise_quote")
def rfq_revise_quote(request: Request, rfq_id: uuid.UUID, form: FormData = Depends(form_data),
                     db: Session = Depends(get_db), user: User = Depends(require_seller_company)):
    q = quotation_repository.get_by_rfq_and_seller(db, rfq_id, user.company_id)
    if q is None:
        return _back(request, rfq_id, error="You have no quotation on this RFQ.")
    try:
        quotation_service.revise_quotation(db, q, _payload(form), user)
    except (ValidationError, QuotationActionError) as exc:
        db.rollback()
        return _back(request, rfq_id, error=exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc))
    return _back(request, rfq_id, msg=f"Quotation revised (revision {q.revision_no}). The buyer was notified.")
