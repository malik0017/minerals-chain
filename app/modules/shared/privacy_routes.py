"""
app/modules/shared/privacy_routes.py
"""
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_required
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.audit_log import AuditLog
from app.models.data_request import DataRequest, DataRequestType
from app.models.user import User
from app.repositories import audit_log_repository
from app.services import data_request_service as drs

router = APIRouter(prefix="/my-profile/privacy", tags=["privacy"])


@router.get("", name="my_privacy")
def privacy_page(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user_required),
                 msg: str | None = None, error: str | None = None):
    context = build_portal_context(user, user.role, active_path=None)
    context.update({
        "requests": db.query(DataRequest).filter(DataRequest.user_id == user.id).order_by(DataRequest.created_at.desc()).all(),
        "types": list(DataRequestType), "msg": msg, "error": error, "u": user,
    })
    return templates.TemplateResponse(request, "shared/privacy.html", context)


@router.get("/export.json", name="my_privacy_export")
def export(db: Session = Depends(get_db), user: User = Depends(get_current_user_required)):
    data = drs.export_user_data(db, user)
    audit_log_repository.create(db, AuditLog(actor_user_id=user.id, action="personal_data_exported",
                                             target_type="user", target_id=user.id))
    db.commit()
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="my-data.json"', "Cache-Control": "no-store"})


@router.post("/request", name="my_privacy_request")
def submit(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user_required),
           request_type: str = Form(...), details: str = Form("")):
    from urllib.parse import quote
    try:
        req = drs.create_request(db, user, request_type, details)
    except drs.DataRequestError as exc:
        db.rollback()
        return RedirectResponse(url=f"{request.url_for('my_privacy')}?error={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"{request.url_for('my_privacy')}?msg={quote(f'Request {req.reference} submitted. We will respond by {req.due_at:%Y-%m-%d}.')}",
                            status_code=303)
