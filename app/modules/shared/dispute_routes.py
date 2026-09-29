"""
app/modules/shared/dispute_routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.permissions import require_buyer_company, require_seller_company
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.dispute import Dispute, DisputeMessage, DisputeStatus
from app.models.order import Order
from app.models.user import User, UserRole
from app.services import dispute_service as ds
from app.services import private_files


def _redirect(url: str, *, msg: str | None = None, error: str | None = None) -> RedirectResponse:
    if error:
        url += ("&" if "?" in url else "?") + "error=" + quote(error)
    elif msg:
        url += ("&" if "?" in url else "?") + "msg=" + quote(msg)
    return RedirectResponse(url=url, status_code=303)


def make_router(party: str) -> APIRouter:
    guard = require_buyer_company if party == "buyer" else require_seller_company
    role = UserRole.BUYER if party == "buyer" else UserRole.SELLER
    base = f"/{party}/disputes"
    router = APIRouter(prefix=base, tags=[f"{party}-disputes"])

    def _own(db: Session, dispute_id: uuid.UUID, user: User) -> Dispute | None:
        d = db.get(Dispute, dispute_id)
        if d is None:
            return None
        o = d.order
        owner = o.buyer_company_id if party == "buyer" else o.seller_company_id
        return d if owner == user.company_id else None

    def _order(db: Session, order_id: uuid.UUID, user: User) -> Order | None:
        o = db.get(Order, order_id)
        if o is None:
            return None
        owner = o.buyer_company_id if party == "buyer" else o.seller_company_id
        return o if owner == user.company_id else None

    @router.get("", name=f"{party}_disputes")
    def index(request: Request, db: Session = Depends(get_db), user: User = Depends(guard),
              status: str = "", page: int = 1):
        col = Order.buyer_company_id if party == "buyer" else Order.seller_company_id
        q = db.query(Dispute).join(Order, Dispute.order_id == Order.id).filter(col == user.company_id)
        if status == "active":
            q = q.filter(Dispute.status.in_([DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW, DisputeStatus.AWAITING_INFO]))
        elif status in {s.value for s in DisputeStatus}:
            q = q.filter(Dispute.status == DisputeStatus(status))
        rows, total, page, pages = paginate(q.order_by(Dispute.created_at.desc()), page)
        ctx = build_portal_context(user, role, active_path=base)
        ctx.update({"rows": rows, "total": total, "page": page, "pages": pages, "qs": qs(status=status),
                    "status": status, "statuses": list(DisputeStatus), "party": party,
                    "categories": ds.CATEGORIES})
        return templates.TemplateResponse(request, "shared/disputes_index.html", ctx)

    @router.get("/new", name=f"{party}_dispute_new")
    def new(request: Request, order_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(guard),
            error: str | None = None):
        o = _order(db, order_id, user)
        if o is None:
            return RedirectResponse(url=request.url_for(f"{party}_disputes"), status_code=303)
        ok, why = ds.can_raise(db, o)
        ctx = build_portal_context(user, role, active_path=base)
        ctx.update({"order": o, "can_raise": ok, "why": why, "categories": ds.CATEGORIES, "party": party,
                    "error": error})
        return templates.TemplateResponse(request, "shared/dispute_new.html", ctx)

    @router.post("/new", name=f"{party}_dispute_create")
    def create(request: Request, order_id: uuid.UUID = Form(...), category: str = Form(""),
               reason: str = Form(""), desired_outcome: str = Form(""), evidence: UploadFile | None = File(None),
               db: Session = Depends(get_db), user: User = Depends(guard)):
        o = _order(db, order_id, user)
        if o is None:
            return RedirectResponse(url=request.url_for(f"{party}_disputes"), status_code=303)
        try:
            d = ds.raise_dispute(db, o, user, category, reason, desired_outcome, evidence)
        except ds.DisputeError as exc:
            db.rollback()
            return _redirect(f"{base}/new?order_id={order_id}", error=str(exc))
        return _redirect(f"{base}/{d.id}", msg="Dispute raised. The platform team and the other party were notified.")

    @router.get("/{dispute_id}", name=f"{party}_dispute_detail")
    def detail(request: Request, dispute_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(guard),
               msg: str | None = None, error: str | None = None):
        d = _own(db, dispute_id, user)
        if d is None:
            return RedirectResponse(url=request.url_for(f"{party}_disputes"), status_code=303)
        ctx = build_portal_context(user, role, active_path=base)
        ctx.update({"d": d, "party": party, "messages": ds.visible_messages(d, party), "categories": ds.CATEGORIES,
                    "is_raiser": d.raised_by_company_id == user.company_id, "msg": msg, "error": error})
        return templates.TemplateResponse(request, "shared/dispute_detail.html", ctx)

    @router.post("/{dispute_id}/message", name=f"{party}_dispute_message")
    def message(request: Request, dispute_id: uuid.UUID, body: str = Form(""),
                evidence: UploadFile | None = File(None), db: Session = Depends(get_db), user: User = Depends(guard)):
        d = _own(db, dispute_id, user)
        if d is None:
            return RedirectResponse(url=request.url_for(f"{party}_disputes"), status_code=303)
        try:
            ds.post_message(db, d, user, party, body, upload=evidence)
        except ds.DisputeError as exc:
            db.rollback()
            return _redirect(f"{base}/{dispute_id}", error=str(exc))
        return _redirect(f"{base}/{dispute_id}", msg="Message sent.")

    @router.post("/{dispute_id}/withdraw", name=f"{party}_dispute_withdraw")
    def withdraw(request: Request, dispute_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(guard)):
        d = _own(db, dispute_id, user)
        if d is None:
            return RedirectResponse(url=request.url_for(f"{party}_disputes"), status_code=303)
        try:
            ds.withdraw(db, d, user)
        except ds.DisputeError as exc:
            db.rollback()
            return _redirect(f"{base}/{dispute_id}", error=str(exc))
        return _redirect(f"{base}/{dispute_id}", msg="Dispute withdrawn. The order continues from where it was.")

    @router.get("/{dispute_id}/files/{message_id}", name=f"{party}_dispute_file")
    def file(dispute_id: uuid.UUID, message_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(guard)):
        d = _own(db, dispute_id, user)
        m = db.get(DisputeMessage, message_id)
        if d is None or m is None or m.dispute_id != d.id or m.is_internal or not m.attachment_path:
            return Response(status_code=404)
        return serve_attachment(m)

    return router


def serve_attachment(m: DisputeMessage) -> Response:
    try:
        data, intact = private_files.read_verified(m.attachment_path, m.attachment_hash)
    except private_files.FileError:
        return Response(status_code=404)
    name = (m.attachment_name or "evidence").replace('"', "")
    return Response(content=data, media_type=private_files.mime_for(m.attachment_path),
                    headers={"Content-Disposition": f'inline; filename="{name}"',
                             "X-Integrity": "verified" if intact else "MISMATCH"})


buyer_router = make_router("buyer")
seller_router = make_router("seller")
