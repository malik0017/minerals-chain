"""
app/modules/shared/shipment_views.py
"""
import csv
import io

from fastapi import Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.models.shipment import SHIPMENT_STATUSES, TRANSPORT_MODES
from app.models.user import User, UserRole
from app.services import shipment_service as svc

ORDER_URL = {UserRole.ADMIN: "/admin/orders/", UserRole.SELLER: "/seller/orders/", UserRole.BUYER: "/buyer/orders/"}


def _scope(role: UserRole, user: User) -> dict:
    if role == UserRole.SELLER:
        return {"seller_id": user.company_id}
    if role == UserRole.BUYER:
        return {"buyer_id": user.company_id}
    return {}


def page(request: Request, db: Session, user: User, role: UserRole, base: str, status: str, q: str, page_no: int):
    scope = _scope(role, user)
    rows, total, page_no, pages = paginate(svc.listing(db, status=status, q=q, **scope), page_no)
    ctx = build_portal_context(user, role, active_path=base)
    ctx.update({"rows": rows, "total": total, "page": page_no, "pages": pages, "qs": qs(status=status, q=q),
                "status": status, "q": q, "s": svc.stats(db, **scope), "labels": SHIPMENT_STATUSES, "modes": TRANSPORT_MODES,
                "order_url": ORDER_URL[role], "base": base, "show_parties": role == UserRole.ADMIN})
    return templates.TemplateResponse(request, "shared/shipments.html", ctx)


def export_csv(db: Session, user: User, role: UserRole, status: str, q: str):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["reference", "order", "status", "mode", "carrier", "tracking", "vehicle", "driver", "origin", "destination",
                "dispatched_at", "eta", "delivered_at", "gross_t", "tare_t", "net_t", "received_t"])
    for s in svc.listing(db, status=status, q=q, **_scope(role, user)).all():
        w.writerow([s.reference, s.order.order_reference or s.order_id, s.status, s.transport_mode, s.carrier_name, s.tracking_number,
                    s.vehicle_plate, s.driver_name, s.origin, s.destination, s.dispatched_at.isoformat(),
                    s.eta.isoformat() if s.eta else "", s.delivered_at.isoformat() if s.delivered_at else "",
                    s.gross_weight_t, s.tare_weight_t, s.net_weight_t, s.received_net_t])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="shipments.csv"'})
