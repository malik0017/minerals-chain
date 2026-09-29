"""
app/modules/admin/disputes/routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.permissions import admin_can, require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.dispute import Dispute, DisputeMessage, DisputeStatus
from app.models.order import Order
from app.models.user import User, UserRole
from app.modules.shared.dispute_routes import serve_attachment
from app.services import dispute_service as ds

router = APIRouter(prefix="/admin/disputes", tags=["admin-disputes"])


def _back(dispute_id, *, msg=None, error=None):
    url = f"/admin/disputes/{dispute_id}"
    if error:
        url += "?error=" + quote(error)
    elif msg:
        url += "?msg=" + quote(msg)
    return RedirectResponse(url=url, status_code=303)


@router.get("", name="admin_disputes")
def queue(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("disputes")),
          status: str = "", category: str = "", q: str = "", mine: str = "", page: int = 1):
    query = db.query(Dispute).join(Order, Dispute.order_id == Order.id)
    if status == "active":
        query = query.filter(Dispute.status.in_([DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW,
                                                 DisputeStatus.AWAITING_INFO]))
    elif status in {s.value for s in DisputeStatus}:
        query = query.filter(Dispute.status == DisputeStatus(status))
    if category in ds.CATEGORIES:
        query = query.filter(Dispute.category == category)
    if mine:
        query = query.filter(Dispute.assigned_admin_id == admin.id)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Dispute.reference.ilike(like), Order.order_reference.ilike(like)))
    rows, total, page, pages = paginate(query.order_by(Dispute.created_at.desc()), page)
    counts = dict(db.query(Dispute.status, func.count()).group_by(Dispute.status).all())
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/disputes")
    ctx.update({"rows": rows, "total": total, "page": page, "pages": pages,
                "qs": qs(status=status, category=category, q=q, mine=mine),
                "status": status, "category": category, "q": q, "mine": mine,
                "statuses": list(DisputeStatus), "categories": ds.CATEGORIES,
                "counts": {s.value: counts.get(s, 0) for s in DisputeStatus}})
    return templates.TemplateResponse(request, "admin/disputes.html", ctx)


@router.get("/{dispute_id}", name="admin_dispute_detail")
def detail(request: Request, dispute_id: uuid.UUID, db: Session = Depends(get_db),
           admin: User = Depends(require_admin("disputes")), msg: str | None = None, error: str | None = None):
    d = db.get(Dispute, dispute_id)
    if d is None:
        return RedirectResponse(url=request.url_for("admin_disputes"), status_code=303)
    admins = [u for u in db.query(User).filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
              .order_by(User.full_name) if admin_can(u, "disputes")]
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/disputes")
    ctx.update({"d": d, "messages": ds.visible_messages(d, "admin"), "categories": ds.CATEGORIES,
                "admins": admins, "msg": msg, "error": error,
                "history": [x for x in ds.for_order(db, d.order) if x.id != d.id]})
    return templates.TemplateResponse(request, "admin/dispute_detail.html", ctx)


@router.post("/{dispute_id}/message", name="admin_dispute_message")
def message(dispute_id: uuid.UUID, body: str = Form(""), internal: str = Form(""),
            evidence: UploadFile | None = File(None), db: Session = Depends(get_db),
            admin: User = Depends(require_admin("disputes"))):
    d = db.get(Dispute, dispute_id)
    if d is None:
        return RedirectResponse(url="/admin/disputes", status_code=303)
    try:
        ds.post_message(db, d, admin, "admin", body, internal=bool(internal), upload=evidence)
    except ds.DisputeError as exc:
        db.rollback()
        return _back(dispute_id, error=str(exc))
    return _back(dispute_id, msg="Internal note saved." if internal else "Message sent to both parties.")


@router.post("/{dispute_id}/status", name="admin_dispute_status")
def status(dispute_id: uuid.UUID, status: str = Form(...), assigned_admin_id: str = Form(""),
           db: Session = Depends(get_db), admin: User = Depends(require_admin("disputes"))):
    d = db.get(Dispute, dispute_id)
    if d is None:
        return RedirectResponse(url="/admin/disputes", status_code=303)
    try:
        ds.set_status(db, d, admin, status, uuid.UUID(assigned_admin_id) if assigned_admin_id else None)
    except (ds.DisputeError, ValueError) as exc:
        db.rollback()
        return _back(dispute_id, error=str(exc))
    return _back(dispute_id, msg="Updated.")


@router.post("/{dispute_id}/decide", name="admin_dispute_decide")
def decide(dispute_id: uuid.UUID, ruling: str = Form(""), decision_text: str = Form(""),
           db: Session = Depends(get_db), admin: User = Depends(require_admin("disputes"))):
    d = db.get(Dispute, dispute_id)
    if d is None:
        return RedirectResponse(url="/admin/disputes", status_code=303)
    try:
        ds.decide(db, d, admin, ruling, decision_text)
    except ds.DisputeError as exc:
        db.rollback()
        return _back(dispute_id, error=str(exc))
    return _back(dispute_id, msg="Decision recorded. It is now permanent and can only be changed by a logged correction.")


@router.post("/{dispute_id}/correct", name="admin_dispute_correct")
def correct(dispute_id: uuid.UUID, ruling: str = Form(""), decision_text: str = Form(""), reason: str = Form(""),
            db: Session = Depends(get_db), admin: User = Depends(require_admin("disputes"))):
    d = db.get(Dispute, dispute_id)
    if d is None:
        return RedirectResponse(url="/admin/disputes", status_code=303)
    try:
        ds.correct_ruling(db, d, admin, ruling, decision_text, reason)
    except ds.DisputeError as exc:
        db.rollback()
        return _back(dispute_id, error=str(exc))
    return _back(dispute_id, msg="Correction logged.")


@router.get("/{dispute_id}/files/{message_id}", name="admin_dispute_file")
def file(dispute_id: uuid.UUID, message_id: uuid.UUID, db: Session = Depends(get_db),
         admin: User = Depends(require_admin("disputes"))):
    m = db.get(DisputeMessage, message_id)
    if m is None or m.dispute_id != dispute_id or not m.attachment_path:
        return Response(status_code=404)
    return serve_attachment(m)
