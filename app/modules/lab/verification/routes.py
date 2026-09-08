"""
app/modules/lab/verification/routes.py

The lab portal's first real feature. Every route gated by
require_lab_company — real lab, approved company only, no admin
bypass (same reasoning as require_seller_company).
"""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.permissions import require_lab_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import certificate_repository, verification_repository
from app.schemas.verification import IssueCertificateRequest, RejectVerificationRequest
from app.services.verification_service import (
    VerificationActionError,
    get_owned_lab_request,
    issue_certificate,
    reject_verification,
)

router = APIRouter(prefix="/lab/verification-requests", tags=["lab-verification"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="lab_verification_index")
def verification_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_lab_company),
):
    requests = verification_repository.list_for_lab_company(db, user.company_id)
    context = build_portal_context(user, UserRole.LAB, active_path=request.url.path)
    context["requests"] = requests
    return templates.TemplateResponse(request, "lab/verification_index.html", context)


@router.get("/{request_id}", name="lab_verification_detail")
def verification_detail(
    request: Request,
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_lab_company),
    error: str | None = None,
):
    try:
        vr = get_owned_lab_request(db, request_id, user.company_id)
    except VerificationActionError:
        return RedirectResponse(url=request.url_for("lab_verification_index"), status_code=303)

    certificate = certificate_repository.get_by_verification_request_id(db, vr.id)

    context = build_portal_context(user, UserRole.LAB, active_path="/lab/verification-requests")
    context.update({"vr": vr, "certificate": certificate, "error": error})
    return templates.TemplateResponse(request, "lab/verification_detail.html", context)


@router.post("/{request_id}/issue", name="lab_verification_issue")
def verification_issue(
    request: Request,
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_lab_company),
    tested_parameters_notes: str = Form(...),
):
    try:
        vr = get_owned_lab_request(db, request_id, user.company_id)
        payload = IssueCertificateRequest(tested_parameters_notes=tested_parameters_notes)
        issue_certificate(db, vr, user, payload.tested_parameters_notes)
    except (VerificationActionError, ValidationError) as exc:
        db.rollback()
        msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(
            url=f"{request.url_for('lab_verification_detail', request_id=request_id)}?error={msg}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("lab_verification_detail", request_id=request_id), status_code=303)


@router.post("/{request_id}/reject", name="lab_verification_reject")
def verification_reject(
    request: Request,
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_lab_company),
    rejection_reason: str = Form(...),
):
    try:
        vr = get_owned_lab_request(db, request_id, user.company_id)
        payload = RejectVerificationRequest(rejection_reason=rejection_reason)
        reject_verification(db, vr, user, payload.rejection_reason)
    except (VerificationActionError, ValidationError) as exc:
        db.rollback()
        msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
        return RedirectResponse(
            url=f"{request.url_for('lab_verification_detail', request_id=request_id)}?error={msg}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("lab_verification_detail", request_id=request_id), status_code=303)
