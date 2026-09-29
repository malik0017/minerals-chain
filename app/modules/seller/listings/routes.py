"""
app/modules/seller/listings/routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.permissions import require_seller_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.certification import CertificationType
from app.models.company import ApprovalStatus, CompanyRole
from app.models.user import User, UserRole
from app.services import spec_service
from app.repositories import certification_repository, company_repository, product_repository, verification_repository
from app.schemas.product import ProductRequest
from app.services.certification_service import CertificationActionError, request_passport
from app.services.product_service import ProductActionError, create_listing, get_owned_listing, update_listing
from app.services.verification_service import VerificationActionError, request_verification

router = APIRouter(prefix="/seller/listings", tags=["seller-listings"])
from app.core.templates import templates


_CATALOG_FIELDS = ("product_master_id", "name_ar", "region_id", "min_order_qty", "incoterm_id",
                   "packaging_type_id", "mine_source_id")


def _catalog_options(db: Session) -> dict:
    from app.models.md_commercial import Incoterm
    from app.models.md_locations import MineSource, Region
    from app.models.md_product import ProductMaster
    from app.models.md_units import PackagingType

    def active(model, order):
        return db.query(model).filter(model.is_active.is_(True)).order_by(order).all()
    return {
        "catalog_products": [p for p in active(ProductMaster, ProductMaster.code) if p.status == "active"],
        "regions": active(Region, Region.sort_order),
        "incoterms": active(Incoterm, Incoterm.sort_order),
        "packaging_types": active(PackagingType, PackagingType.sort_order),
        "mine_sources": active(MineSource, MineSource.code),
    }


def _catalog_form(form) -> dict:
    return {k: (form.get(k) or "") for k in _CATALOG_FIELDS}


def _parse_form(
    mineral_type: str, grade: str, specifications_notes: str,
    quantity_value: str, quantity_unit: str,
    price_value: str, price_currency: str, price_unit: str,
    packaging: str, trade_terms: str, catalog: dict | None = None,
) -> tuple[ProductRequest | None, list[str], dict]:
    raw_form = {
        "mineral_type": mineral_type, "grade": grade, "specifications_notes": specifications_notes,
        "quantity_value": quantity_value, "quantity_unit": quantity_unit,
        "price_value": price_value, "price_currency": price_currency, "price_unit": price_unit,
        "packaging": packaging, "trade_terms": trade_terms,
        **(catalog or {}),
    }
    catalog = {k: (v or None) for k, v in (catalog or {}).items()}
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
            **catalog,
        )
        return payload, [], raw_form
    except ValidationError as exc:
        errors = [err["msg"] for err in exc.errors()]
        return None, errors, raw_form


def _spec_rows(form) -> tuple[list[dict], str | None]:
    try:
        return spec_service.parse_rows(form, "spec"), None
    except spec_service.SpecError as exc:
        return [], f"Specification: {exc}"


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
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
    context.update({"errors": [], "form": {}, "mode": "create", **_catalog_options(db)})
    return templates.TemplateResponse(request, "seller/listing_form.html", context)


@router.post("", name="seller_listings_create")
def listings_create(
    request: Request,
    form: FormData = Depends(form_data),
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
        price_value, price_currency, price_unit, packaging, trade_terms, _catalog_form(form),
    )
    spec_rows, spec_error = _spec_rows(form)
    if spec_error:
        payload, errors = None, errors + [spec_error]
    if payload is not None:
        try:
            product = create_listing(db, user.company, payload, created_by=user)
            spec_service.save_product_specs(db, product, spec_rows)  # Batch M3
            db.commit()
        except ProductActionError as exc:
            payload, errors = None, [str(exc)]
    if payload is None:
        context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
        context.update({"errors": errors, "form": raw_form, "mode": "create", "spec_rows": spec_rows, **_catalog_options(db)})
        return templates.TemplateResponse(request, "seller/listing_form.html", context, status_code=422)

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
    from app.services.lab_partner_service import lab_options
    context["available_labs"] = lab_options(db)  
    lab_certs = certification_repository.list_for_product(db, product.id, cert_type=CertificationType.LAB_CERTIFICATE)
    context["certificate"] = next((c for c in lab_certs if c.status.value == "approved"), None)
    context["passport_history"] = certification_repository.list_for_product(db, product.id, cert_type=CertificationType.MINERAL_PASSPORT)
    from datetime import date as _date
    from app.core.system_settings import get_setting as _gs
    context["spec_rows"] = spec_service.product_rows(db, product)
    context["renewal_window"] = _gs(db, "passport_renewal_window_days")
    context["today"] = _date.today()
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
        request_passport(db, product, scope)
    except (ProductActionError, CertificationActionError) as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('seller_listing_detail', product_id=product_id)}?error={exc}",
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
            **{k: ("" if getattr(product, k) is None else str(getattr(product, k))) for k in _CATALOG_FIELDS},
        },
        "spec_rows": spec_service.product_rows(db, product),
        **_catalog_options(db),
    })
    return templates.TemplateResponse(request, "seller/listing_form.html", context)


@router.post("/{product_id}/edit", name="seller_listing_edit_submit")
def listing_edit_submit(
    request: Request,
    product_id: uuid.UUID,
    form: FormData = Depends(form_data),
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
        price_value, price_currency, price_unit, packaging, trade_terms, _catalog_form(form),
    )
    spec_rows, spec_error = _spec_rows(form)
    if spec_error:
        payload, errors = None, errors + [spec_error]
    if payload is None:
        context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
        context.update({"errors": errors, "form": raw_form, "mode": "edit", "product": product, "spec_rows": spec_rows,
                        **_catalog_options(db)})
        return templates.TemplateResponse(request, "seller/listing_form.html", context, status_code=422)

    try:
        update_listing(db, product, payload)
        spec_service.save_product_specs(db, product, spec_rows)  # Batch M3
        db.commit()
    except ProductActionError as exc:
        db.rollback()
        context = build_portal_context(user, UserRole.SELLER, active_path="/seller/listings")
        context.update({"errors": [str(exc)], "form": raw_form, "mode": "edit", "product": product,
                        "spec_rows": spec_rows, **_catalog_options(db)})
        return templates.TemplateResponse(request, "seller/listing_form.html", context, status_code=400)

    return RedirectResponse(url=request.url_for("seller_listing_detail", product_id=product.id), status_code=303)
