"""
app/services/shipment_service.py
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.order import Order, OrderStatus
from app.models.shipment import OPEN_STATUSES, SHIPMENT_STATUSES, TRANSPORT_MODES, Shipment, ShipmentEvent
from app.models.user import User
from app.services import notification_service, reference_service

UPDATE_STATUSES = ("in_transit", "at_checkpoint", "delayed", "arrived", "delivered")
STATUS_AR = {"dispatched": "تم الإرسال", "in_transit": "قيد النقل", "at_checkpoint": "عند نقطة تفتيش", "delayed": "متأخرة",
             "arrived": "وصلت إلى الموقع", "delivered": "تم التسليم", "cancelled": "ملغاة"}


class ShipmentError(ValueError):
    pass


def _clean(v, n=150):
    v = (v or "").strip()
    return v[:n] or None


def _dec(v, label):
    if v in (None, ""):
        return None
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        raise ShipmentError(f"{label} must be a number.")
    if d < 0:
        raise ShipmentError(f"{label} can't be negative.")
    return d


def _dt(v):
    if not v:
        return None
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        raise ShipmentError("Invalid date.")
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _event(db, s: Shipment, status: str, location, note, user: User | None, at: datetime | None = None):
    ev = ShipmentEvent(shipment_id=s.id, status=status, location=_clean(location), note=_clean(note, 1000),
                       occurred_at=at or datetime.now(timezone.utc), created_by_user_id=user.id if user else None)
    db.add(ev)
    return ev


def for_order(db: Session, order: Order) -> list[Shipment]:
    return db.query(Shipment).filter(Shipment.order_id == order.id).order_by(Shipment.dispatched_at).all()


def dispatch(db: Session, order: Order, form, user: User | None) -> Shipment:
    from app.services import order_service
    mode = form.get("transport_mode") or "truck"
    if mode not in TRANSPORT_MODES:
        raise ShipmentError("Choose a transport mode.")
    gross, tare = _dec(form.get("gross_weight_t"), "Gross weight"), _dec(form.get("tare_weight_t"), "Tare weight")
    if gross is not None and tare is not None and tare > gross:
        raise ShipmentError("Tare weight can't exceed gross weight.")
    eta = _dt(form.get("eta"))
    now = datetime.now(timezone.utc)
    if eta is None and order.quotation and order.quotation.lead_time_days:
        eta = now + timedelta(days=int(order.quotation.lead_time_days))
    s = Shipment(reference=reference_service.next_reference(db, "shipment"), order_id=order.id,
                 seller_company_id=order.seller_company_id, buyer_company_id=order.buyer_company_id,
                 status="dispatched", transport_mode=mode, carrier_name=_clean(form.get("carrier_name")),
                 tracking_number=_clean(form.get("tracking_number"), 80), vehicle_plate=_clean(form.get("vehicle_plate"), 30),
                 driver_name=_clean(form.get("driver_name"), 120), driver_phone=_clean(form.get("driver_phone"), 30),
                 origin=_clean(form.get("origin")), destination=_clean(form.get("destination")) or order.delivery_location or (order.rfq.delivery_location if order.rfq else None),
                 weighbridge_ticket=_clean(form.get("weighbridge_ticket"), 60), gross_weight_t=gross, tare_weight_t=tare,
                 dispatched_at=_dt(form.get("dispatched_at")) or now, eta=eta, notes=_clean(form.get("notes"), 2000),
                 created_by_user_id=user.id if user else None)
    db.add(s)
    db.flush()
    _event(db, s, "dispatched", s.origin, "Loaded and dispatched" + (f" · ticket {s.weighbridge_ticket}" if s.weighbridge_ticket else ""), user, s.dispatched_at)
    if user:
        db.add(AuditLog(actor_user_id=user.id, action="shipment_dispatched", target_type="order", target_id=order.id,
                        details=f"{s.reference} {mode} {s.carrier_name or ''} {s.vehicle_plate or ''}".strip()))
    if order.status == OrderStatus.CONFIRMED:
        order_service.mark_shipped(db, order)
    else:
        db.commit()
    db.refresh(s)
    return s


def add_update(db: Session, shipment: Shipment, form, user: User | None) -> ShipmentEvent:
    from app.services import order_service
    status = form.get("status") or ""
    if shipment.status in ("delivered", "cancelled"):
        raise ShipmentError("This shipment is closed.")
    if status not in UPDATE_STATUSES:
        raise ShipmentError("Choose a tracking status.")
    ev = _event(db, shipment, status, form.get("location"), form.get("note"), user, _dt(form.get("occurred_at")))
    shipment.status = status
    new_eta = _dt(form.get("eta"))
    if new_eta:
        shipment.eta = new_eta
    if status == "delivered":
        shipment.delivered_at = ev.occurred_at
        shipment.received_net_t = _dec(form.get("received_net_t"), "Received weight") or shipment.received_net_t
    order = shipment.order
    notification_service.notify_company(
        db, shipment.buyer_company, "shipment_update", f"Shipment {shipment.reference}: {SHIPMENT_STATUSES[status]}",
        f"{SHIPMENT_STATUSES[status]}" + (f" — {ev.location}" if ev.location else ""),
        action_url=f"/buyer/orders/{order.id}", shipment=shipment.reference, status_ar=STATUS_AR[status],
        where=f"— {ev.location}" if ev.location else "")
    if user:
        db.add(AuditLog(actor_user_id=user.id, action="shipment_update", target_type="order", target_id=order.id,
                        details=f"{shipment.reference} → {status}"))
    if status == "delivered" and order.status == OrderStatus.IN_TRANSIT:
        order_service.mark_delivered(db, order)
    else:
        db.commit()
    return ev


def close_for_order(db: Session, order: Order) -> None:
    db.flush()
    now = datetime.now(timezone.utc)
    for s in db.query(Shipment).filter(Shipment.order_id == order.id, Shipment.status.in_(OPEN_STATUSES)).all():
        s.status, s.delivered_at = "delivered", now
        _event(db, s, "delivered", s.destination, "Order marked delivered", None, now)


def get_scoped(db: Session, shipment_id, company: Company | None, side: str | None = None) -> Shipment | None:
    try:
        s = db.get(Shipment, uuid.UUID(str(shipment_id)))
    except ValueError:
        return None
    if s is None or company is None:
        return s
    owner = s.seller_company_id if side == "seller" else s.buyer_company_id
    return s if owner == company.id else None


def _scoped(db: Session, seller_id=None, buyer_id=None):
    query = db.query(Shipment)
    if seller_id:
        query = query.filter(Shipment.seller_company_id == seller_id)
    if buyer_id:
        query = query.filter(Shipment.buyer_company_id == buyer_id)
    return query


def listing(db: Session, *, seller_id=None, buyer_id=None, status: str = "", q: str = ""):
    query = _scoped(db, seller_id, buyer_id)
    if status == "late":
        query = query.filter(Shipment.status.in_(OPEN_STATUSES), Shipment.eta < datetime.now(timezone.utc))
    elif status:
        query = query.filter(Shipment.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(Shipment.reference.ilike(like) | Shipment.carrier_name.ilike(like)
                             | Shipment.vehicle_plate.ilike(like) | Shipment.tracking_number.ilike(like))
    return query.order_by(Shipment.dispatched_at.desc())


def stats(db: Session, seller_id=None, buyer_id=None) -> dict:
    base = _scoped(db, seller_id, buyer_id)
    now = datetime.now(timezone.utc)
    by_status = dict(base.with_entities(Shipment.status, func.count()).group_by(Shipment.status).all())
    by_mode = dict(base.with_entities(Shipment.transport_mode, func.count()).group_by(Shipment.transport_mode).all())
    carriers = (base.with_entities(func.coalesce(Shipment.carrier_name, "—"), func.count())
                .group_by(Shipment.carrier_name).order_by(func.count().desc()).limit(8).all())
    delivered = base.filter(Shipment.status == "delivered", Shipment.delivered_at.isnot(None)).all()
    on_time = sum(1 for s in delivered if not s.eta or s.delivered_at <= s.eta)
    hours = [(s.delivered_at - s.dispatched_at).total_seconds() / 3600 for s in delivered]
    return {
        "total": sum(by_status.values()),
        "open": sum(by_status.get(k, 0) for k in OPEN_STATUSES),
        "late": base.filter(Shipment.status.in_(OPEN_STATUSES), Shipment.eta < now).count(),
        "delivered": len(delivered),
        "on_time_pct": round(100 * on_time / len(delivered)) if delivered else None,
        "avg_transit_h": round(sum(hours) / len(hours), 1) if hours else None,
        "by_status": [{"name": SHIPMENT_STATUSES[k], "value": v} for k, v in by_status.items() if k in SHIPMENT_STATUSES],
        "by_mode": [{"name": TRANSPORT_MODES.get(k, k), "value": v} for k, v in by_mode.items()],
        "carriers": [{"name": k, "value": v} for k, v in carriers],
    }
