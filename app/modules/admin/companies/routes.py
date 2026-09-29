"""
app/modules/admin/companies/routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.permissions import require_admin, require_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.certification import CertificationType
from app.models.company import ApprovalStatus, CompanyRole
from app.models.user import User, UserRole
from app.repositories import certification_repository, company_repository, product_repository, verification_repository

router = APIRouter(prefix="/admin/companies", tags=["admin-companies"])
from app.core.templates import templates


@router.get("", name="admin_companies_list")
def companies_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin("companies")),
    role: str | None = None,
    status: str | None = None,
    q: str = "",
    tier: str = "",
    page: int = 1,
):
    from sqlalchemy import func, or_
    from app.core.listing import paginate, qs
    from app.models.company import Company, SubscriptionTier
    query = db.query(Company)
    if role in [r.value for r in CompanyRole]:
        query = query.filter(Company.role == CompanyRole(role))
    if status in [s_.value for s_ in ApprovalStatus]:
        query = query.filter(Company.status == ApprovalStatus(status))
    if tier in [t_.value for t_ in SubscriptionTier]:
        query = query.filter(Company.subscription_tier == SubscriptionTier(tier))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Company.company_name.ilike(like), Company.company_name_ar.ilike(like),
                                 Company.cr_number.ilike(like), Company.contact_email.ilike(like)))
    companies, total, page, pages = paginate(query.order_by(Company.created_at.desc()), page, 30)
    counts = dict(db.query(Company.role, func.count()).group_by(Company.role).all())

    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context.update({
        "companies": companies, "role_filter": role, "status_filter": status, "q": q, "tier": tier,
        "roles": list(CompanyRole), "statuses": list(ApprovalStatus), "tiers": list(SubscriptionTier),
        "total": total, "page": page, "pages": pages, "qs": qs(role=role, status=status, q=q, tier=tier),
        "role_counts": {k.value: v for k, v in counts.items()},
    })
    return templates.TemplateResponse(request, "admin/companies_list.html", context)


@router.get("/new", name="admin_company_new")
def company_new(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("companies")),
                error: str | None = None):
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/companies")
    context.update({"error": error})
    context.update(company_admin_context(db))
    return templates.TemplateResponse(request, "admin/company_new.html", context)


@router.post("/new", name="admin_company_create")
def company_create(request: Request, form: FormData = Depends(form_data), db: Session = Depends(get_db),
                   admin: User = Depends(require_admin("companies"))):
    """Batch Q1: onboard a company on its behalf (e.g. a signed paper application)."""
    from urllib.parse import quote
    try:
        company = cc.admin_create_company(db, admin, dict(form))
    except (cc.ControlCenterError, ValueError) as exc:
        db.rollback()
        return RedirectResponse(url=f"{request.url_for('admin_company_new')}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=request.url_for("admin_company_detail", company_id=company.id), status_code=303)


@router.get("/{company_id}", name="admin_company_detail")
def company_detail(
    request: Request,
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin("companies")),
    msg: str | None = None,
    error: str | None = None,
):
    company = company_repository.get_by_id(db, company_id)
    if company is None:
        return RedirectResponse(url=request.url_for("admin_companies_list"), status_code=303)

    users = company.users
    products = []
    verification_counts = {}
    certificates = []
    passports = []

    if company.role == CompanyRole.SELLER:
        products = product_repository.list_for_company(db, company.id)
        for p in products:
            verification_counts[p.id] = len(verification_repository.list_for_product(db, p.id))
        passports = certification_repository.list_for_subject_company(db, company.id, cert_type=CertificationType.MINERAL_PASSPORT)
    elif company.role == CompanyRole.LAB:
        certificates = certification_repository.list_for_issuing_company(db, company.id)

    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/companies")
    context.update({
        "company": company,
        "company_users": users,
        "products": products,
        "verification_counts": verification_counts,
        "certificates": certificates,
        "passports": passports,
        "msg": msg,
        "error": error,
    })
    context.update(company_admin_context(db))  # Batch K
    from app.services import company_document_service, credential_check_service
    context.update({"cred": credential_check_service.panel(db, company),
                    "library": company_document_service.checklist(db, company)})
    return templates.TemplateResponse(request, "admin/company_detail.html", context)

from urllib.parse import quote  
from fastapi.responses import FileResponse  
from app.models.md_commercial import CustomerSegment  
from app.models.md_locations import Region 
from app.models.company import SubscriptionTier  
from app.services import control_center_service as cc  
from app.services.document_upload_service import resolve_document_path  


def _detail_redirect(request: Request, company_id, msg=None, error=None):
    url = str(request.url_for("admin_company_detail", company_id=company_id))
    q = "&".join(x for x in (f"msg={quote(msg)}" if msg else "", f"error={quote(error)}" if error else "") if x)
    return RedirectResponse(url=url + (f"?{q}" if q else ""), status_code=303)


def company_admin_context(db: Session) -> dict:
    """Extra context company_detail.html needs for the Batch K admin forms."""
    return {
        "regions": db.query(Region).filter(Region.is_active.is_(True)).order_by(Region.sort_order).all(),
        "segments": db.query(CustomerSegment).filter(CustomerSegment.is_active.is_(True)).order_by(CustomerSegment.sort_order).all(),
        "tiers": list(SubscriptionTier),
        "company_statuses": list(ApprovalStatus),
    }


@router.post("/{company_id}/edit", name="admin_company_edit")
def company_edit(request: Request, company_id: uuid.UUID, form: FormData = Depends(form_data), db: Session = Depends(get_db),
                       admin: User = Depends(require_admin("companies"))):
    company = company_repository.get_by_id(db, company_id)
    if company is None:
        return RedirectResponse(url=request.url_for("admin_companies_list"), status_code=303)
    try:
        cc.update_company(db, company, dict(form), admin)
    except (cc.ControlCenterError, ValueError) as exc:
        db.rollback()
        return _detail_redirect(request, company_id, error=str(exc))
    return _detail_redirect(request, company_id, msg="Company saved.")


@router.post("/{company_id}/status", name="admin_company_status")
def company_status(request: Request, company_id: uuid.UUID, form: FormData = Depends(form_data), db: Session = Depends(get_db),
                         admin: User = Depends(require_admin("companies"))):
    company = company_repository.get_by_id(db, company_id)
    if company is None:
        return RedirectResponse(url=request.url_for("admin_companies_list"), status_code=303)
    try:
        cc.change_company_status(db, company, ApprovalStatus(form.get("status")), admin, form.get("reason"))
    except (cc.ControlCenterError, ValueError) as exc:
        db.rollback()
        return _detail_redirect(request, company_id, error=str(exc))
    return _detail_redirect(request, company_id, msg=f"Company is now {company.status.value}.")


@router.get("/{company_id}/documents/{kind}", name="admin_company_document")
def company_document(company_id: uuid.UUID, kind: str, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin("companies"))):
    company = company_repository.get_by_id(db, company_id)
    filename = None
    if company is not None:
        filename = {"cr": company.cr_document_filename, "license": company.license_document_filename}.get(kind)
    path = resolve_document_path(filename) if filename else None
    if path is None:
        return RedirectResponse(url=f"/admin/companies/{company_id}?error=" + quote("Document file not found."), status_code=303)
    from app.services import file_crypto
    from app.services.private_files import mime_for
    try:
        data = file_crypto.read(path)
    except file_crypto.FileCryptoError as exc:
        return RedirectResponse(url=f"/admin/companies/{company_id}?error=" + quote(str(exc)), status_code=303)
    return Response(content=data, media_type=mime_for(path.name),
                    headers={"Content-Disposition": f'inline; filename="{company.cr_number}-{kind}{path.suffix}"',
                             "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
