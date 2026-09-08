"""
app/modules/seller/listings/routes.py
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
from app.models.company import ApprovalStatus, CompanyRole
from app.models.passport import PassportScope
from app.models.user import User, UserRole
from app.repositories import certificate_repository, company_repository, passport_repository, product_repository, verification_repository
from app.schemas.product import ProductRequest
from app.services.passport_service import PassportActionError, request_passport
from app.services.product_service import ProductActionError, create_listing, get_owned_listing, update_listing
from app.services.verification_service import VerificationActionError, request_verification

router = APIRouter(prefix="/seller/listings", tags=["seller-listings"])
templates = Jinja2Templates(directory="app/templates")


def _parse_form(
    mineral_type: str, grade: str, specifications_notes: str,
    quantity_value: str, quantity_unit: str,
    price_value: str, price_currency: str, price_unit: str,
    packaging: str, trade_terms: str,
) -> tuple[ProductRequest | None, list[str], dict]:
    """Shared between create and edit — parses raw form strings into
    ProductRequest, returning (payload_or_None, error_messages, raw_form_for_redisplay)."""
    raw_form = {
        "mineral_type": mineral_type, "grade": grade, "specifications_notes": specifications_notes,
        "quantity_value": quantity_value, "quantity_unit": quantity_unit,
        "price_value": price_value, "price_currency": price_currency, "price_unit": price_unit,
        "packaging": packaging, "trade_terms": trade_terms,
    }
    try:
        payload = ProductRequest(
            mineral_type=mineral_type,
            grade=grade or None,
            specifications_notes=specifications_notes or None,
            quantity_value=quantity_value,
            quantity_unit=quantity_unit or "MT",
            price_value=price_value or None,
            price_currency=price_currency or "SAR",
            price_unit=price_unit or None,
            packaging=packaging or None,
            trade_terms=trade_terms or None,
        )
        return payload, [], raw_form
    except ValidationError as exc:
        errors = [err["msg"] for err in exc.errors()]
        return None, errors, raw_form


@router.get("", name="seller_listings_index")
def listings_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    products = product_repository.list_for_company(db, user.company_id)
    context = build_portal_context(user, UserRole.SELLER, active_path=request.url.path)
    context["products"] = products
    return templates.TemplateResponse(request, "seller/listings_index.html", context)


@router.get("/new", name="seller_listings_new")
def listings_new(
    request: Request,
    user: User = Depends(require_seller_company),
):
    context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
    context.update({"errors": [], "form": {}, "mode": "create"})
    return templates.TemplateResponse(request, "seller/listing_form.html", context)


@router.post("", name="seller_listings_create")
def listings_create(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    mineral_type: str = Form(...),
    grade: str = Form(""),
    specifications_notes: str = Form(""),
    quantity_value: str = Form(...),
    quantity_unit: str = Form("MT"),
    price_value: str = Form(""),
    price_currency: str = Form("SAR"),
    price_unit: str = Form(""),
    packaging: str = Form(""),
    trade_terms: str = Form(""),
):
    payload, errors, raw_form = _parse_form(
        mineral_type, grade, specifications_notes, quantity_value, quantity_unit,
        price_value, price_currency, price_unit, packaging, trade_terms,
    )
    if payload is None:
        context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
        context.update({"errors": errors, "form": raw_form, "mode": "create"})
        return templates.TemplateResponse(request, "seller/listing_form.html", context, status_code=422)

    product = create_listing(db, user.company, payload)
    return RedirectResponse(url=request.url_for("seller_listing_detail", product_id=product.id), status_code=303)


@router.get("/{product_id}", name="seller_listing_detail")
def listing_detail(
    request: Request,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    error: str | None = None,
):
    try:
        product = get_owned_listing(db, product_id, user.company_id)
    except ProductActionError:
        return RedirectResponse(url=request.url_for("seller_listings_index"), status_code=303)

    context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
    context["product"] = product
    context["error"] = error
    context["verification_history"] = verification_repository.list_for_product(db, product.id)
    context["available_labs"] = company_repository.list_all(db, role=CompanyRole.LAB, status=ApprovalStatus.APPROVED)
    context["certificate"] = None
    for vr in context["verification_history"]:
        if vr.status.value == "completed":
            context["certificate"] = certificate_repository.get_by_verification_request_id(db, vr.id)
            break
    context["passport_history"] = passport_repository.list_for_product(db, product.id)
    return templates.TemplateResponse(request, "seller/listing_detail.html", context)


@router.post("/{product_id}/request-passport", name="seller_listing_request_passport")
def listing_request_passport(
    request: Request,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    scope: str = Form(...),
):
    try:
        product = get_owned_listing(db, product_id, user.company_id)
        scope_value = PassportScope(scope)
        request_passport(db, product, scope_value)
    except (ProductActionError, PassportActionError) as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('seller_listing_detail', product_id=product_id)}?error={exc}",
            status_code=303,
        )
    except ValueError:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('seller_listing_detail', product_id=product_id)}?error=Invalid scope selected.",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("seller_listing_detail", product_id=product_id), status_code=303)


@router.post("/{product_id}/request-verification", name="seller_listing_request_verification")
def listing_request_verification(
    request: Request,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    lab_company_id: uuid.UUID = Form(...),
):
    try:
        product = get_owned_listing(db, product_id, user.company_id)
        lab_company = company_repository.get_by_id(db, lab_company_id)
        if lab_company is None:
            raise VerificationActionError("Selected lab not found.")
        request_verification(db, product, lab_company, user)
    except (ProductActionError, VerificationActionError) as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('seller_listing_detail', product_id=product_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("seller_listing_detail", product_id=product_id), status_code=303)


@router.get("/{product_id}/edit", name="seller_listing_edit_form")
def listing_edit_form(
    request: Request,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    try:
        product = get_owned_listing(db, product_id, user.company_id)
    except ProductActionError:
        return RedirectResponse(url=request.url_for("seller_listings_index"), status_code=303)

    context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
    context.update({
        "errors": [], "mode": "edit", "product": product,
        "form": {
            "mineral_type": product.mineral_type, "grade": product.grade or "",
            "specifications_notes": product.specifications_notes or "",
            "quantity_value": str(product.quantity_value), "quantity_unit": product.quantity_unit,
            "price_value": str(product.price_value) if product.price_value is not None else "",
            "price_currency": product.price_currency, "price_unit": product.price_unit or "",
            "packaging": product.packaging or "", "trade_terms": product.trade_terms or "",
        },
    })
    return templates.TemplateResponse(request, "seller/listing_form.html", context)


@router.post("/{product_id}/edit", name="seller_listing_edit_submit")
def listing_edit_submit(
    request: Request,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    mineral_type: str = Form(...),
    grade: str = Form(""),
    specifications_notes: str = Form(""),
    quantity_value: str = Form(...),
    quantity_unit: str = Form("MT"),
    price_value: str = Form(""),
    price_currency: str = Form("SAR"),
    price_unit: str = Form(""),
    packaging: str = Form(""),
    trade_terms: str = Form(""),
):
    try:
        product = get_owned_listing(db, product_id, user.company_id)
    except ProductActionError:
        return RedirectResponse(url=request.url_for("seller_listings_index"), status_code=303)

    payload, errors, raw_form = _parse_form(
        mineral_type, grade, specifications_notes, quantity_value, quantity_unit,
        price_value, price_currency, price_unit, packaging, trade_terms,
    )
    if payload is None:
        context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
        context.update({"errors": errors, "form": raw_form, "mode": "edit", "product": product})
        return templates.TemplateResponse(request, "seller/listing_form.html", context, status_code=422)

    try:
        update_listing(db, product, payload)
    except ProductActionError as exc:
        db.rollback()
        context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
        context.update({"errors": [str(exc)], "form": raw_form, "mode": "edit", "product": product})
        return templates.TemplateResponse(request, "seller/listing_form.html", context, status_code=400)

    return RedirectResponse(url=request.url_for("seller_listing_detail", product_id=product.id), status_code=303)
