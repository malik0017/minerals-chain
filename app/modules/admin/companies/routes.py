"""
app/modules/admin/companies/routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.permissions import require_portal
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.company import ApprovalStatus, CompanyRole
from app.models.user import User, UserRole
from app.repositories import certificate_repository, company_repository, passport_repository, product_repository, verification_repository

router = APIRouter(prefix="/admin/companies", tags=["admin-companies"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="admin_companies_list")
def companies_list(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
    role: str | None = None,
    status: str | None = None,
):
    role_filter = CompanyRole(role) if role in [r.value for r in CompanyRole] else None
    status_filter = ApprovalStatus(status) if status in [s.value for s in ApprovalStatus] else None

    companies = company_repository.list_all(db, role=role_filter, status=status_filter)

    context = build_portal_context(admin, UserRole.ADMIN, active_path=request.url.path)
    context.update({
        "companies": companies,
        "role_filter": role,
        "status_filter": status,
        "roles": list(CompanyRole),
        "statuses": list(ApprovalStatus),
    })
    return templates.TemplateResponse(request, "admin/companies_list.html", context)


@router.get("/{company_id}", name="admin_company_detail")
def company_detail(
    request: Request,
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_portal(UserRole.ADMIN)),
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
        passports = passport_repository.list_for_company(db, company.id)
    elif company.role == CompanyRole.LAB:
        certificates = certificate_repository.list_for_lab_company(db, company.id)

    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/companies")
    context.update({
        "company": company,
        "company_users": users,
        "products": products,
        "verification_counts": verification_counts,
        "certificates": certificates,
        "passports": passports,
    })
    return templates.TemplateResponse(request, "admin/company_detail.html", context)
