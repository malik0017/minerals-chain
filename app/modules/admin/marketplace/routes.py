"""
app/modules/admin/marketplace/routes.py
"""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.company import Company
from app.models.product import Product, ProductStatus
from app.models.quotation import Quotation
from app.models.rfq import RFQ, RFQStatus
from app.models.user import User, UserRole
from app.services import marketplace_admin_service as mas, quotation_service, rfq_service, spec_service

router = APIRouter(tags=["admin-marketplace"])


def _to(url: str, *, msg=None, error=None):
    sep = "&" if "?" in url else "?"
    if error:
        url += f"{sep}error={quote(error)}"
    elif msg:
        url += f"{sep}msg={quote(msg)}"
    return RedirectResponse(url=url, status_code=303)


@router.get("/admin/products", name="admin_products")
def products(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("products")),
             q: str = "", status: str = "", page: int = 1, msg: str | None = None, error: str | None = None):
    query = db.query(Product).join(Company, Company.id == Product.seller_company_id)
    if status in {s.value for s in ProductStatus}:
        query = query.filter(Product.status == ProductStatus(status))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Product.mineral_type.ilike(like), Product.grade.ilike(like), Company.company_name.ilike(like)))
    rows, total, page, pages = paginate(query.order_by(Product.updated_at.desc()), page)
    counts = dict(db.query(Product.status, func.count()).group_by(Product.status).all())
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/products")
    ctx.update({"rows": rows, "total": total, "page": page, "pages": pages, "qs": qs(q=q, status=status),
                "q": q, "status": status, "statuses": list(ProductStatus), "msg": msg, "error": error,
                "counts": {s.value: counts.get(s, 0) for s in ProductStatus}})
    return templates.TemplateResponse(request, "admin/products.html", ctx)


@router.post("/admin/products/{product_id}/suspend", name="admin_product_suspend")
def product_suspend(product_id: uuid.UUID, reason: str = Form(""), back: str = Form("/admin/products"),
                    db: Session = Depends(get_db), admin: User = Depends(require_admin("products"))):
    back = back if back.startswith("/admin/") else "/admin/products"
    p = db.get(Product, product_id)
    if p is None:
        return _to(back, error="Listing not found.")
    try:
        mas.suspend_product(db, p, admin, reason)
    except mas.MarketplaceAdminError as exc:
        db.rollback()
        return _to(back, error=str(exc))
    return _to(back, msg=f"{p.mineral_type} suspended.")


@router.post("/admin/products/{product_id}/reactivate", name="admin_product_reactivate")
def product_reactivate(product_id: uuid.UUID, back: str = Form("/admin/products"), db: Session = Depends(get_db),
                       admin: User = Depends(require_admin("products"))):
    back = back if back.startswith("/admin/") else "/admin/products"
    p = db.get(Product, product_id)
    if p is None:
        return _to(back, error="Listing not found.")
    try:
        mas.reactivate_product(db, p, admin)
    except mas.MarketplaceAdminError as exc:
        db.rollback()
        return _to(back, error=str(exc))
    return _to(back, msg=f"{p.mineral_type} reactivated ({p.status.value.replace('_', ' ')}).")


@router.get("/admin/rfqs", name="admin_rfqs")
def rfqs(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("rfqs")),
         q: str = "", status: str = "", page: int = 1, msg: str | None = None, error: str | None = None):
    quotation_service.expire_stale(db)
    query = db.query(RFQ).join(Company, Company.id == RFQ.buyer_company_id)
    if status in {s.value for s in RFQStatus}:
        query = query.filter(RFQ.status == RFQStatus(status))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(RFQ.mineral_type.ilike(like), RFQ.rfq_reference.ilike(like), Company.company_name.ilike(like)))
    rows, total, page, pages = paginate(query.order_by(RFQ.created_at.desc()), page)
    ids = [r.id for r in rows]
    stats = {rid: (n, best) for rid, n, best in db.query(Quotation.rfq_id, func.count(), func.min(Quotation.total_price))
             .filter(Quotation.rfq_id.in_(ids)).group_by(Quotation.rfq_id)} if ids else {}
    counts = dict(db.query(RFQ.status, func.count()).group_by(RFQ.status).all())
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/rfqs")
    ctx.update({"rows": rows, "total": total, "page": page, "pages": pages, "qs": qs(q=q, status=status),
                "q": q, "status": status, "statuses": list(RFQStatus), "stats": stats, "msg": msg, "error": error,
                "counts": {s.value: counts.get(s, 0) for s in RFQStatus}})
    return templates.TemplateResponse(request, "admin/rfqs.html", ctx)


@router.get("/admin/rfqs/{rfq_id}", name="admin_rfq_detail")
def rfq_detail(request: Request, rfq_id: uuid.UUID, db: Session = Depends(get_db),
               admin: User = Depends(require_admin("rfqs")), msg: str | None = None, error: str | None = None):
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        return _to("/admin/rfqs", error="RFQ not found.")
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/rfqs")
    ctx.update({"rfq": rfq, "rows": quotation_service.comparison(db, rfq), "spec_rows": rfq_service.spec_rows(rfq),
                "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin/rfq_detail.html", ctx)


@router.post("/admin/rfqs/{rfq_id}/cancel", name="admin_rfq_cancel")
def rfq_cancel(rfq_id: uuid.UUID, reason: str = Form(""), db: Session = Depends(get_db),
               admin: User = Depends(require_admin("rfqs"))):
    rfq = db.get(RFQ, rfq_id)
    if rfq is None:
        return _to("/admin/rfqs", error="RFQ not found.")
    try:
        rfq_service.cancel_rfq(db, rfq, admin, f"[Platform] {reason.strip()}" if reason.strip() else "")
    except rfq_service.RFQActionError as exc:
        db.rollback()
        return _to(f"/admin/rfqs/{rfq_id}", error=str(exc))
    return _to(f"/admin/rfqs/{rfq_id}", msg="RFQ cancelled.")
