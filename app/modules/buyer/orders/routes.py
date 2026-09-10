"""
app/modules/buyer/orders/routes.py

BRD §6.6. Gated by require_buyer_company. Identity reveal is handled
entirely through core/identity_guard.py — see order_detail() below for
exactly where that's applied.
"""
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.identity_guard import is_identity_revealed
from app.core.permissions import require_buyer_company
from app.core.portal_nav import build_portal_context
from app.database.base import get_db
from app.models.user import User, UserRole
from app.repositories import order_repository
from app.services.order_service import OrderActionError, confirm_receipt, get_owned_order

router = APIRouter(prefix="/buyer/orders", tags=["buyer-orders"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", name="buyer_orders_index")
def orders_index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
):
    orders = order_repository.list_for_buyer_company(db, user.company_id)
    context = build_portal_context(user, UserRole.BUYER, active_path=request.url.path)
    context["orders"] = [(o, is_identity_revealed(o)) for o in orders]
    return templates.TemplateResponse(request, "buyer/orders_index.html", context)


@router.get("/{order_id}", name="buyer_order_detail")
def order_detail(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
    error: str | None = None,
):
    try:
        order = get_owned_order(db, order_id, user.company_id, "buyer")
    except OrderActionError:
        return RedirectResponse(url=request.url_for("buyer_orders_index"), status_code=303)

    revealed = is_identity_revealed(order)
    context = build_portal_context(user, UserRole.BUYER, active_path="/buyer/orders")
    context.update({
        "order": order,
        "revealed": revealed,
        # Only ever pass the seller company into the template once
        # revealed — see identity_guard.py's docstring for why this
        # matters more than just hiding it in the HTML.
        "seller_company": order.seller_company if revealed else None,
        "error": error,
    })
    return templates.TemplateResponse(request, "buyer/order_detail.html", context)


@router.post("/{order_id}/confirm-receipt", name="buyer_order_confirm_receipt")
def order_confirm_receipt(
    request: Request,
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_buyer_company),
):
    try:
        order = get_owned_order(db, order_id, user.company_id, "buyer")
        confirm_receipt(db, order)
    except OrderActionError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"{request.url_for('buyer_order_detail', order_id=order_id)}?error={exc}",
            status_code=303,
        )
    return RedirectResponse(url=request.url_for("buyer_order_detail", order_id=order_id), status_code=303)
