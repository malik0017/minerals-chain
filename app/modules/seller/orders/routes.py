"""
app/modules/seller/orders/routes.py

BRD §6.6. Gated by require_seller_company. confirm_order() here is
THE route that triggers identity reveal — see order_service.py.
"""
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.identity_guard import is_identity_revealed
from app.core.permissions import require_seller_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import order_repository
from app.services.order_service import OrderActionError, confirm_order, get_owned_order, mark_delivered, mark_shipped

router = APIRouter(prefix="/seller/orders", tags=["seller-orders"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="seller_orders_index")
def orders_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    orders = order_repository.list_for_seller_company(db, user.company_id)
    context = build_portal_context(user, UserRole.SELLER, active_path=request.url.path)
    context["orders"] = [(o, is_identity_revealed(o)) for o in orders]
    return templates.TemplateResponse(request, "seller/orders_index.html", context)


@router.get("/{order_id}", name="seller_order_detail")
def order_detail(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
    error: str | None = None,
):
    try:
        order = get_owned_order(db, order_id, user.company_id, "seller")
    except OrderActionError:
        return RedirectResponse(url=request.url_for("seller_orders_index"), status_code=303)

    revealed = is_identity_revealed(order)
    context = build_portal_context(user, UserRole.SELLER, active_path="/seller/orders")
    context.update({
        "order": order,
        "revealed": revealed,
        "buyer_company": order.buyer_company if revealed else None,
        "error": error,
    })
    return templates.TemplateResponse(request, "seller/order_detail.html", context)


@router.post("/{order_id}/confirm", name="seller_order_confirm")
def order_confirm(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    try:
        order = get_owned_order(db, order_id, user.company_id, "seller")
        confirm_order(db, order)
    except OrderActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('seller_order_detail', order_id=order_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("seller_order_detail", order_id=order_id), status_code=303)


@router.post("/{order_id}/ship", name="seller_order_ship")
def order_ship(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    try:
        order = get_owned_order(db, order_id, user.company_id, "seller")
        mark_shipped(db, order)
    except OrderActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('seller_order_detail', order_id=order_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("seller_order_detail", order_id=order_id), status_code=303)


@router.post("/{order_id}/mark-delivered", name="seller_order_mark_delivered")
def order_mark_delivered(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_seller_company),
):
    try:
        order = get_owned_order(db, order_id, user.company_id, "seller")
        mark_delivered(db, order)
    except OrderActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('seller_order_detail', order_id=order_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("seller_order_detail", order_id=order_id), status_code=303)
