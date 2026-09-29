"""
app/modules/api/v1.py
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.exceptions import RateLimitExceededException
from app.core.identity_guard import is_identity_revealed
from app.database.base import get_db
from app.models.api_token import ApiToken
from app.models.notification import Notification
from app.models.order import Order
from app.models.product import Product, ProductStatus
from app.models.rfq import RFQ
from app.models.shipment import SHIPMENT_STATUSES, Shipment
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/v1", tags=["api-v1"])
RATE = {"max_attempts": 120, "window_seconds": 60}


class ApiContext:
    def __init__(self, user: User, token: ApiToken):
        self.user, self.token = user, token

    @property
    def role(self) -> str:
        return self.user.role.value

    def require(self, scope: str) -> None:
        if scope not in (self.token.scopes or []):
            raise HTTPException(status_code=403, detail=f"Token lacks the '{scope}' scope.")


def api_auth(request: Request, db: Session = Depends(get_db)) -> ApiContext:
    from app.services import api_token_service
    header = request.headers.get("authorization", "")
    raw = header[7:].strip() if header.lower().startswith("bearer ") else ""
    from app.core.client_ip import client_ip
    ip = client_ip(request)
    found = api_token_service.authenticate(db, raw, ip)
    if found is None:
        raise HTTPException(status_code=401, detail="Missing, invalid, expired or revoked API token.",
                            headers={"WWW-Authenticate": "Bearer"})
    user, token = found
    try:
        rate_limit.check("api", token.prefix, **RATE)
    except RateLimitExceededException as exc:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.", headers={"Retry-After": str(exc.retry_after_seconds)})
    return ApiContext(user, token)


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def _dt(v):
    return v.isoformat() if v else None


def _page(query, page: int, size: int):
    size = max(1, min(size, 100))
    page = max(1, page)
    total = query.order_by(None).count()
    return query.offset((page - 1) * size).limit(size).all(), {"page": page, "size": size, "total": total}


def _party(ctx: ApiContext, order: Order) -> str:
    if ctx.user.role == UserRole.ADMIN:
        return "admin"
    if order.buyer_company_id == ctx.user.company_id:
        return "buyer"
    if order.seller_company_id == ctx.user.company_id:
        return "seller"
    raise HTTPException(status_code=404, detail="Order not found.")


def _order_json(ctx: ApiContext, o: Order, db: Session | None = None) -> dict:
    party = _party(ctx, o)
    revealed = is_identity_revealed(o)
    counterparty = None
    if party == "admin":
        counterparty = {"buyer": o.buyer_company.company_name, "seller": o.seller_company.company_name}
    elif revealed:
        c = o.seller_company if party == "buyer" else o.buyer_company
        counterparty = {"name": c.company_name, "email": c.contact_email, "phone": c.contact_phone}
    out = {"id": str(o.id), "reference": o.order_reference, "status": o.status.value, "role": party,
           "mineral": o.rfq.mineral_type if o.rfq else None, "quantity": _num(o.quantity), "unit": o.quantity_unit,
           "price_per_unit": _num(o.price_per_unit), "currency": o.currency, "total_sar": _num(o.total_value_sar),
           "delivery_location": o.delivery_location or (o.rfq.delivery_location if o.rfq else None),
           "identity_revealed": revealed, "counterparty": counterparty,
           "created_at": _dt(o.created_at), "confirmed_at": _dt(o.confirmed_at), "shipped_at": _dt(o.shipped_at),
           "delivered_at": _dt(o.delivered_at), "completed_at": _dt(o.completed_at)}
    if db is not None:
        from app.services import shipment_service
        out["shipments"] = [_shipment_json(s, True) for s in shipment_service.for_order(db, o)]
    return out


def _shipment_json(s: Shipment, events: bool = False) -> dict:
    out = {"id": str(s.id), "reference": s.reference, "order_id": str(s.order_id), "status": s.status,
           "status_label": SHIPMENT_STATUSES.get(s.status, s.status), "mode": s.transport_mode, "carrier": s.carrier_name,
           "tracking_number": s.tracking_number, "vehicle_plate": s.vehicle_plate, "driver": s.driver_name,
           "origin": s.origin, "destination": s.destination, "net_weight_t": _num(s.net_weight_t),
           "received_net_t": _num(s.received_net_t), "dispatched_at": _dt(s.dispatched_at), "eta": _dt(s.eta),
           "delivered_at": _dt(s.delivered_at), "late": s.is_late and s.status != "delivered"}
    if events:
        out["events"] = [{"status": e.status, "location": e.location, "note": e.note, "at": _dt(e.occurred_at)} for e in s.events]
    return out


@router.get("/me", summary="Current user, company and token")
def me(ctx: ApiContext = Depends(api_auth)):
    u, c = ctx.user, ctx.user.company
    return {"id": str(u.id), "name": u.full_name, "email": u.email, "role": ctx.role, "language": u.preferred_language,
            "company": {"id": str(c.id), "name": c.company_name, "role": c.role.value,
                        "tier": c.subscription_tier.value if c.subscription_tier else None} if c else None,
            "token": {"name": ctx.token.name, "scopes": ctx.token.scopes, "expires_at": _dt(ctx.token.expires_at)}}


@router.get("/dashboard", summary="Headline numbers for the home screen")
def dashboard(ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db)):
    from app.models.order import OrderStatus
    q = db.query(Order)
    if ctx.user.role == UserRole.SELLER:
        q = q.filter(Order.seller_company_id == ctx.user.company_id)
    elif ctx.user.role == UserRole.BUYER:
        q = q.filter(Order.buyer_company_id == ctx.user.company_id)
    open_states = (OrderStatus.PENDING_CONFIRMATION, OrderStatus.CONFIRMED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED, OrderStatus.INVOICED)
    sq = db.query(Shipment)
    if ctx.user.role == UserRole.SELLER:
        sq = sq.filter(Shipment.seller_company_id == ctx.user.company_id)
    elif ctx.user.role == UserRole.BUYER:
        sq = sq.filter(Shipment.buyer_company_id == ctx.user.company_id)
    return {"orders_open": q.filter(Order.status.in_(open_states)).count(),
            "orders_awaiting_confirmation": q.filter(Order.status == OrderStatus.PENDING_CONFIRMATION).count(),
            "shipments_in_transit": sq.filter(Shipment.status.in_(("dispatched", "in_transit", "at_checkpoint", "delayed", "arrived"))).count(),
            "unread_notifications": db.query(Notification).filter(Notification.user_id == ctx.user.id, Notification.is_read.is_(False)).count()}


@router.get("/notifications", summary="Notifications (newest first)")
def notifications(ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db),
                  unread: bool = False, page: int = 1, size: int = 25, lang: str = Query("en", pattern="^(en|ar)$")):
    from app.services.notification_service import localized
    q = db.query(Notification).filter(Notification.user_id == ctx.user.id)
    if unread:
        q = q.filter(Notification.is_read.is_(False))
    rows, meta = _page(q.order_by(Notification.created_at.desc()), page, size)
    items = []
    for n in rows:
        title, body = localized(n, lang)
        items.append({"id": str(n.id), "type": n.type, "title": title, "body": body, "url": n.action_url,
                      "read": n.is_read, "created_at": _dt(n.created_at)})
    return {"items": items, **meta}


@router.post("/notifications/{notification_id}/read", summary="Mark a notification read")
def notification_read(notification_id: uuid.UUID, ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db)):
    ctx.require("write")
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != ctx.user.id:
        raise HTTPException(status_code=404, detail="Notification not found.")
    n.is_read, n.read_at = True, datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.get("/orders", summary="Orders visible to the caller")
def orders(ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db), status: str = "", page: int = 1, size: int = 25):
    q = db.query(Order)
    if ctx.user.role == UserRole.SELLER:
        q = q.filter(Order.seller_company_id == ctx.user.company_id)
    elif ctx.user.role == UserRole.BUYER:
        q = q.filter(Order.buyer_company_id == ctx.user.company_id)
    elif ctx.user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Orders are not available to this role.")
    if status:
        q = q.filter(Order.status == status)
    rows, meta = _page(q.order_by(Order.created_at.desc()), page, size)
    return {"items": [_order_json(ctx, o) for o in rows], **meta}


@router.get("/orders/{order_id}", summary="One order with its shipments")
def order(order_id: uuid.UUID, ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return _order_json(ctx, o, db)


def _shipment_scope(ctx: ApiContext, db: Session):
    q = db.query(Shipment)
    if ctx.user.role == UserRole.SELLER:
        return q.filter(Shipment.seller_company_id == ctx.user.company_id)
    if ctx.user.role == UserRole.BUYER:
        return q.filter(Shipment.buyer_company_id == ctx.user.company_id)
    if ctx.user.role == UserRole.ADMIN:
        return q
    raise HTTPException(status_code=403, detail="Shipments are not available to this role.")


@router.get("/shipments", summary="Shipments visible to the caller")
def shipments(ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db), status: str = "", page: int = 1, size: int = 25):
    q = _shipment_scope(ctx, db)
    if status:
        q = q.filter(Shipment.status == status)
    rows, meta = _page(q.order_by(Shipment.dispatched_at.desc()), page, size)
    return {"items": [_shipment_json(s) for s in rows], **meta}


@router.get("/shipments/{shipment_id}", summary="One shipment with its tracking timeline")
def shipment(shipment_id: uuid.UUID, ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db)):
    s = _shipment_scope(ctx, db).filter(Shipment.id == shipment_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    return _shipment_json(s, True)


@router.post("/shipments/{shipment_id}/events", status_code=201, summary="Post a tracking update (seller)")
def shipment_event(shipment_id: uuid.UUID, payload: dict = Body(..., examples=[{"status": "at_checkpoint", "location": "Al Khurmah", "note": ""}]),
                   ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db)):
    from app.services import shipment_service
    from app.services.order_service import OrderActionError
    ctx.require("write")
    if ctx.user.role != UserRole.SELLER:
        raise HTTPException(status_code=403, detail="Only the seller can post tracking updates.")
    s = shipment_service.get_scoped(db, shipment_id, ctx.user.company, "seller")
    if s is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    try:
        shipment_service.add_update(db, s, {k: str(v) for k, v in payload.items() if v is not None}, ctx.user)
    except (shipment_service.ShipmentError, OrderActionError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.refresh(s)
    return _shipment_json(s, True)


@router.get("/rfqs", summary="Buyer: own RFQs · Seller: open RFQ inbox")
def rfqs(ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db), page: int = 1, size: int = 25):
    from app.models.rfq import RFQStatus
    q = db.query(RFQ)
    if ctx.user.role == UserRole.BUYER:
        q = q.filter(RFQ.buyer_company_id == ctx.user.company_id)
    elif ctx.user.role == UserRole.SELLER:
        q = q.filter(RFQ.status == RFQStatus.OPEN)
    elif ctx.user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="RFQs are not available to this role.")
    rows, meta = _page(q.order_by(RFQ.created_at.desc()), page, size)
    own = ctx.user.role in (UserRole.BUYER, UserRole.ADMIN)
    from sqlalchemy import func
    from app.models.quotation import Quotation
    quotes = dict(db.query(Quotation.rfq_id, func.count()).filter(Quotation.rfq_id.in_([r.id for r in rows]))
                  .group_by(Quotation.rfq_id).all()) if own and rows else {}
    return {"items": [{"id": str(r.id), "reference": r.rfq_reference, "mineral": r.mineral_type, "quantity": _num(r.quantity_value),
                       "unit": r.quantity_unit, "delivery_location": r.delivery_location, "timeframe": r.delivery_timeframe,
                       "status": r.status.value, "closes_at": _dt(r.closes_at), "created_at": _dt(r.created_at),
                       "quotes": quotes.get(r.id, 0) if own else None} for r in rows], **meta}


@router.get("/listings", summary="Seller: own listings · Buyer: verified marketplace (seller identity hidden)")
def listings(ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db), q: str = "", page: int = 1, size: int = 25):
    query = db.query(Product)
    own = ctx.user.role == UserRole.SELLER
    if own:
        query = query.filter(Product.seller_company_id == ctx.user.company_id)
    elif ctx.user.role in (UserRole.BUYER, UserRole.ADMIN):
        query = query.filter(Product.status == ProductStatus.VERIFIED, Product.is_visible_to_buyers.is_(True))
    else:
        raise HTTPException(status_code=403, detail="Listings are not available to this role.")
    if q:
        query = query.filter(Product.mineral_type.ilike(f"%{q.strip()}%") | Product.grade.ilike(f"%{q.strip()}%"))
    rows, meta = _page(query.order_by(Product.updated_at.desc()), page, size)
    return {"items": [{"id": str(p.id), "mineral": p.mineral_type, "grade": p.grade, "quantity": _num(p.quantity_value),
                       "unit": p.quantity_unit, "price": _num(p.price_value), "currency": p.price_currency,
                       "status": p.status.value, "visible": p.is_visible_to_buyers,
                       "seller": p.seller_company.company_name if ctx.user.role == UserRole.ADMIN else None,
                       "updated_at": _dt(p.updated_at)} for p in rows], **meta}


@router.get("/inventory", summary="Seller: stock on hand per listing and warehouse")
def inventory(ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db)):
    from app.services import inventory_service
    if ctx.user.role != UserRole.SELLER:
        raise HTTPException(status_code=403, detail="Inventory is available to sellers only.")
    s = inventory_service.summary(db, ctx.user.company_id)
    return {"on_hand": _num(s["on_hand"]), "reserved": _num(s["reserved"]), "value_sar": _num(s["value"]),
            "products": [{"id": str(e["product"].id), "mineral": e["product"].mineral_type, "grade": e["product"].grade,
                          "on_hand": _num(e["on_hand"]), "reserved": _num(e["reserved"]), "available": _num(e["available"]),
                          "value_sar": _num(e["value"])} for e in s["products"]],
            "warehouses": [{"product_id": str(r["product"].id) if r["product"] else None,
                            "warehouse": r["warehouse"].name_en if r["warehouse"] else None,
                            "on_hand": _num(r["on_hand"]), "avg_cost": _num(r["avg_cost"])} for r in s["rows"]]}


@router.get("/documents", summary="Company compliance documents and expiry health")
def documents(ctx: ApiContext = Depends(api_auth), db: Session = Depends(get_db)):
    from app.services import company_document_service as docs
    if ctx.user.company is None:
        raise HTTPException(status_code=403, detail="No company on this account.")
    rows = docs.checklist(db, ctx.user.company)
    return {"completeness": docs.completeness(rows),
            "items": [{"type": r["type"], "label": r["label"], "required": r["required"], "health": r["health"],
                       "days_left": r["days_left"], "version": r["doc"].version if r["doc"] else None,
                       "review": r["doc"].status if r["doc"] else None,
                       "expires_on": r["doc"].expires_on.isoformat() if r["doc"] and r["doc"].expires_on else None} for r in rows]}
