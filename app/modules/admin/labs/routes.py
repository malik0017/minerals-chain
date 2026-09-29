"""
app/modules/admin/labs/routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.system_settings import get_setting
from app.core.templates import templates
from app.database.base import get_db
from app.models.company import Company, CompanyRole
from app.models.lab_partner import LabPartnerTerms
from app.models.user import User, UserRole
from app.models.verification import VerificationRequest, VerificationStatus
from app.services import lab_partner_service as lps

router = APIRouter(prefix="/admin/labs", tags=["admin-labs"])


@router.get("", name="admin_labs")
def labs(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("labs")),
         msg: str | None = None, error: str | None = None):
    labs = db.query(Company).filter(Company.role == CompanyRole.LAB).order_by(Company.company_name).all()
    terms = {t.lab_company_id: t for t in db.query(LabPartnerTerms)}
    stats = lps.lab_stats(db)
    queue = db.query(VerificationRequest).filter(VerificationRequest.status.in_([
        VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED, VerificationStatus.TESTING_IN_PROGRESS])) \
        .order_by(VerificationRequest.is_priority.desc(), VerificationRequest.created_at).limit(15).all()
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/labs")
    ctx.update({"labs": labs, "terms": terms, "stats": stats, "queue": queue, "msg": msg, "error": error,
                "default_fee": get_setting(db, "lab_verification_fee_sar")})
    return templates.TemplateResponse(request, "admin/labs.html", ctx)


@router.post("/{company_id}/terms", name="admin_lab_terms")
def save_terms(company_id: uuid.UUID, form: FormData = Depends(form_data), db: Session = Depends(get_db),
               admin: User = Depends(require_admin("labs"))):
    lab = db.get(Company, company_id)
    if lab is None:
        return RedirectResponse(url="/admin/labs", status_code=303)
    try:
        lps.save_terms(db, admin, lab, form)
    except lps.LabPartnerError as exc:
        db.rollback()
        return RedirectResponse(url=f"/admin/labs?error={quote(str(exc))}#lab-{company_id}", status_code=303)
    return RedirectResponse(url=f"/admin/labs?msg={quote(lab.company_name + ' terms saved.')}#lab-{company_id}", status_code=303)
