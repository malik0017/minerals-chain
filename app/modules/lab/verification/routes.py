"""
app/modules/lab/verification/routes.py
"""
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from starlette.datastructures import FormData
from urllib.parse import quote

from app.core.forms import form_data
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.permissions import require_lab_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import certification_repository, verification_repository
from app.schemas.verification import IssueCertificateRequest, RejectVerificationRequest
from app.services import spec_service, verification_service as vs
from app.services.verification_service import (
    VerificationActionError,
    get_owned_lab_request,
    issue_certificate,
    reject_verification,
)

router = APIRouter(prefix="/lab/verification-requests", tags=["lab-verification"])
from app.core.templates import templates


@router.get("", name="lab_verification_index")
def verification_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_lab_company),
):
    requests = verification_repository.list_for_lab_company(db, user.company_id)
    context = build_portal_context(user, UserRole.LAB, active_path=request.url.path)
    # Batch M2: active first, premium (priority) first within active, oldest first
    active = ("requested", "sample_scheduled", "testing_in_progress")
    context["requests"] = sorted(requests, key=lambda r: (r.status.value not in active, not r.is_priority,
                                                          r.created_at.timestamp() if r.status.value in active else -r.created_at.timestamp()))
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

    certificate = certification_repository.get_by_verification_request_id(db, vr.id)

    context = build_portal_context(user, UserRole.LAB, active_path="/lab/verification-requests")
    context.update({"vr": vr, "certificate": certificate, "error": error,
                    "spec_rows": spec_service.product_rows(db, vr.product)})
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


def _back(request: Request, request_id, *, error: str | None = None):
    url = str(request.url_for("lab_verification_detail", request_id=request_id))
    return RedirectResponse(url=f"{url}?error={quote(error)}" if error else url, status_code=303)


@router.post("/{request_id}/schedule", name="lab_verification_schedule")
def verification_schedule(request: Request, request_id: uuid.UUID, db: Session = Depends(get_db),
                          user: User = Depends(require_lab_company), collection_date: str = Form(""),
                          field_officer: str = Form(""), sample_id: str = Form("")):
    try:
        vr = get_owned_lab_request(db, request_id, user.company_id)
        vs.schedule_sample(db, vr, user, collection_date, field_officer, sample_id)
    except VerificationActionError as exc:
        db.rollback()
        return _back(request, request_id, error=str(exc))
    return _back(request, request_id)


@router.post("/{request_id}/start-testing", name="lab_verification_start")
def verification_start(request: Request, request_id: uuid.UUID, db: Session = Depends(get_db),
                       user: User = Depends(require_lab_company)):
    try:
        vr = get_owned_lab_request(db, request_id, user.company_id)
        vs.start_testing(db, vr, user)
    except VerificationActionError as exc:
        db.rollback()
        return _back(request, request_id, error=str(exc))
    return _back(request, request_id)


@router.post("/{request_id}/results", name="lab_verification_results")
def verification_results(request: Request, request_id: uuid.UUID, form: FormData = Depends(form_data),
                         db: Session = Depends(get_db), user: User = Depends(require_lab_company)):
    try:
        vr = get_owned_lab_request(db, request_id, user.company_id)
        rows = spec_service.parse_rows(form, "spec")
        measured = form.getlist("spec_measured")
        names = [n for n in form.getlist("spec_param")]
        # keep measured values aligned with the non-empty parameter rows
        aligned = [m for n, m in zip(names, measured) if (n or "").strip()]
        for r, m in zip(rows, aligned):
            r["measured"] = m
        vs.record_results(db, vr, user, rows, form.get("analyst_name", ""), form.get("notes", ""))
    except (VerificationActionError, spec_service.SpecError) as exc:
        db.rollback()
        return _back(request, request_id, error=str(exc))
    return _back(request, request_id)
