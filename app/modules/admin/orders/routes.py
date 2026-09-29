"""
app/modules/admin/orders/routes.py
"""
import uuid
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import require_admin, require_portal
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.order import Order, OrderStatus, RevealLog, SettlementFee, SettlementFeeStatus
from app.models.user import User, UserRole
from app.services import control_center_service as cc

router = APIRouter(tags=["admin-orders"])


def _to(request: Request, name: str, msg=None, error=None, **params):
    url = str(request.url_for(name, **params))
    q = "&".join(x for x in (f"msg={quote(msg)}" if msg else "", f"error={quote(error)}" if error else "") if x)
    return RedirectResponse(url=url + (f"?{q}" if q else ""), status_code=303)


@router.get("/admin/orders", name="admin_orders_list")
def orders_list(request: Request, db: Session = Depends(get_db),
                admin: User = Depends(require_admin("orders")), status: str | None = None):
    query = select(Order).order_by(Order.created_at.desc())
    if status in {s.value for s in OrderStatus}:
        query = query.where(Order.status == OrderStatus(status))
    orders = db.execute(query.limit(500)).scalars().all()
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/orders")
    context.update({"orders": orders, "statuses": list(OrderStatus), "status_filter": status or ""})
    return templates.TemplateResponse(request, "admin/orders_list.html", context)


@router.get("/admin/orders/{order_id}", name="admin_order_detail")
def order_detail(request: Request, order_id: uuid.UUID, db: Session = Depends(get_db),
                 admin: User = Depends(require_admin("orders")),
                 msg: str | None = None, error: str | None = None):
    order = db.get(Order, order_id)
    if order is None:
        return _to(request, "admin_orders_list", error="Order not found.")
    reveals = db.execute(select(RevealLog).where(RevealLog.order_id == order.id).order_by(RevealLog.revealed_at)).scalars().all()
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/orders")
    context.update({"order": order, "reveals": reveals, "statuses": list(OrderStatus),
                    "fee_statuses": list(SettlementFeeStatus), "msg": msg, "error": error})
    from app.services import dispute_service
    context["disputes"] = dispute_service.for_order(db, order)
    from app.services import order_document_service as ods
    context.update({"documents": ods.visible_documents(order, "admin"), "credentials": ods.linked_credentials(db, order),
                    "doc_types": {**ods.DOC_TYPES, **ods.GENERATED_TYPES}})
    return templates.TemplateResponse(request, "admin/order_detail.html", context)


@router.post("/admin/orders/{order_id}/status", name="admin_order_set_status")
def order_set_status(request: Request, order_id: uuid.UUID, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin("orders")),
                     status: str = Form(...), reason: str = Form("")):
    order = db.get(Order, order_id)
    if order is None:
        return _to(request, "admin_orders_list", error="Order not found.")
    try:
        cc.admin_set_order_status(db, order, OrderStatus(status), admin, reason)
    except (cc.ControlCenterError, ValueError) as exc:
        db.rollback()
        return _to(request, "admin_order_detail", error=str(exc), order_id=order_id)
    return _to(request, "admin_order_detail", msg=f"Order is now {status.replace('_', ' ')}.", order_id=order_id)


@router.get("/admin/finance", name="admin_finance")
def finance(request: Request, db: Session = Depends(get_db),
            admin: User = Depends(require_admin("finance")),
            status: str | None = None, msg: str | None = None, error: str | None = None):
    query = select(SettlementFee).order_by(SettlementFee.created_at.desc())
    if status in {s.value for s in SettlementFeeStatus}:
        query = query.where(SettlementFee.status == SettlementFeeStatus(status))
    fees = db.execute(query.limit(500)).scalars().all()
    totals = {s.value: Decimal(db.scalar(select(func.coalesce(func.sum(SettlementFee.total_sar), 0))
                                         .where(SettlementFee.status == s)) or 0) for s in SettlementFeeStatus}
    gmv = db.scalar(select(func.coalesce(func.sum(Order.total_value_sar), 0))
                    .where(Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.PENDING_CONFIRMATION])))
    context = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/finance")
    context.update({"fees": fees, "totals": totals, "gmv": gmv, "fee_statuses": list(SettlementFeeStatus),
                    "status_filter": status or "", "msg": msg, "error": error})
    return templates.TemplateResponse(request, "admin/finance.html", context)


@router.post("/admin/finance/fees/{fee_id}", name="admin_fee_set_status")
def fee_set_status(request: Request, fee_id: uuid.UUID, db: Session = Depends(get_db),
                   admin: User = Depends(require_admin("finance")),
                   status: str = Form(...), reference: str = Form(""), back: str = Form("finance")):
    fee = db.get(SettlementFee, fee_id)
    if fee is None:
        return _to(request, "admin_finance", error="Fee not found.")
    try:
        cc.set_fee_status(db, fee, status, admin, reference.strip() or None)
    except cc.ControlCenterError as exc:
        db.rollback()
        if back == "order":
            return _to(request, "admin_order_detail", error=str(exc), order_id=fee.order_id)
        return _to(request, "admin_finance", error=str(exc))
    if back == "order":
        return _to(request, "admin_order_detail", msg="Fee updated.", order_id=fee.order_id)
    return _to(request, "admin_finance", msg="Fee updated.")
