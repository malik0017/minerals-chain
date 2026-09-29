"""
app/modules/admin/data_requests/routes.py
"""
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.data_request import DataRequest, DataRequestStatus
from app.models.user import User, UserRole
from app.services import data_request_service as drs

router = APIRouter(prefix="/admin/data-requests", tags=["admin-data-requests"])


@router.get("", name="admin_data_requests")
def queue(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("data_requests")),
          status: str = "", page: int = 1):
    q = db.query(DataRequest)
    if status in {s.value for s in DataRequestStatus}:
        q = q.filter(DataRequest.status == DataRequestStatus(status))
    rows, total, page, pages = paginate(q.order_by(DataRequest.due_at.asc()), page)
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/data-requests")
    context.update({"rows": rows, "total": total, "page": page, "pages": pages, "qs": qs(status=status),
                    "status": status, "statuses": list(DataRequestStatus), "now": datetime.now(timezone.utc)})
    return templates.TemplateResponse(request, "admin/data_requests.html", context)


@router.get("/{request_id}", name="admin_data_request_detail")
def detail(request: Request, request_id: uuid.UUID, db: Session = Depends(get_db),
           admin: User = Depends(require_admin("data_requests")), msg: str | None = None, error: str | None = None):
    req = db.get(DataRequest, request_id)
    if req is None:
        return RedirectResponse(url=request.url_for("admin_data_requests"), status_code=303)
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/data-requests")
    context.update({"r": req, "statuses": list(DataRequestStatus), "msg": msg, "error": error,
                    "now": datetime.now(timezone.utc)})
    return templates.TemplateResponse(request, "admin/data_request_detail.html", context)


@router.post("/{request_id}", name="admin_data_request_update")
def update(request: Request, request_id: uuid.UUID, db: Session = Depends(get_db),
           admin: User = Depends(require_admin("data_requests")), status: str = Form(...), response: str = Form("")):
    req = db.get(DataRequest, request_id)
    if req is None:
        return RedirectResponse(url=request.url_for("admin_data_requests"), status_code=303)
    url = str(request.url_for("admin_data_request_detail", request_id=request_id))
    try:
        drs.update_request(db, req, admin, status, response)
    except drs.DataRequestError as exc:
        db.rollback()
        return RedirectResponse(url=f"{url}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"{url}?msg=Saved", status_code=303)


@router.post("/{request_id}/anonymise", name="admin_data_request_anonymise")
def anonymise(request: Request, request_id: uuid.UUID, db: Session = Depends(get_db),
              admin: User = Depends(require_admin("data_requests"))):
    req = db.get(DataRequest, request_id)
    if req is None:
        return RedirectResponse(url=request.url_for("admin_data_requests"), status_code=303)
    url = str(request.url_for("admin_data_request_detail", request_id=request_id))
    try:
        drs.anonymise_user(db, req.user, admin, f"request {req.reference}")
    except drs.DataRequestError as exc:
        db.rollback()
        return RedirectResponse(url=f"{url}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"{url}?msg={quote('Account anonymised and disabled. Mark the request completed with a response.')}", status_code=303)
