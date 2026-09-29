"""
app/services/portal_dashboard_service.py
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.company_document import CompanyDocument
from app.models.order import Order, OrderStatus
from app.models.quotation import Quotation, QuotationStatus
from app.models.rfq import RFQ, RFQStatus
from app.models.shipment import OPEN_STATUSES, Shipment
from app.models.verification import VerificationRequest, VerificationStatus
from app.services.analytics_service import month_keys

LIVE = (OrderStatus.CONFIRMED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED, OrderStatus.INVOICED,
        OrderStatus.COMPLETED, OrderStatus.RESOLVED)


def _since(keys):
    return datetime.strptime(keys[0] + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _docs_attention(db: Session, company: Company) -> int:
    soon = date.today() + timedelta(days=60)
    return db.query(CompanyDocument).filter(CompanyDocument.company_id == company.id, CompanyDocument.is_current.is_(True),
                                            ((CompanyDocument.expires_on <= soon) | (CompanyDocument.status == "rejected"))).count()


def trade(db: Session, company: Company, side: str) -> dict:
    col = Order.seller_company_id if side == "seller" else Order.buyer_company_id
    keys = month_keys(6)
    rows = (db.query(func.to_char(Order.created_at, "YYYY-MM"), func.count(Order.id),
                     func.coalesce(func.sum(Order.total_value_sar), 0))
            .filter(col == company.id, Order.created_at >= _since(keys), Order.status.in_(LIVE))
            .group_by(func.to_char(Order.created_at, "YYYY-MM")).all())
    by = {k: (n, float(v)) for k, n, v in rows}
    recent = db.query(Order).filter(col == company.id).order_by(Order.created_at.desc()).limit(6).all()
    sq = db.query(Shipment).filter((Shipment.seller_company_id if side == "seller" else Shipment.buyer_company_id) == company.id)
    in_transit = sq.filter(Shipment.status.in_(OPEN_STATUSES)).count()
    if side == "seller":
        pending = db.query(Order).filter(col == company.id, Order.status == OrderStatus.PENDING_CONFIRMATION).count()
        to_ship = db.query(Order).filter(col == company.id, Order.status == OrderStatus.CONFIRMED).count()
        quoted = {q for (q,) in db.query(Quotation.rfq_id).filter(Quotation.seller_company_id == company.id).all()}
        from app.repositories import rfq_repository
        from app.services import rfq_service
        open_rfqs = [r.id for r in rfq_repository.list_open(db) if rfq_service.accepting_quotes(r)]
        actions = [
            ("bi-hourglass-split", "Orders to confirm", pending, "warning", "/seller/orders?show=pending_confirmation"),
            ("bi-truck", "Orders to dispatch", to_ship, "primary", "/seller/orders?show=confirmed"),
            ("bi-inbox", "RFQs you haven't quoted", len([r for r in open_rfqs if r not in quoted]), "info", "/seller/rfq-inbox?show=new"),
            ("bi-geo-alt", "Shipments on the road", in_transit, "success", "/seller/shipments"),
            ("bi-folder2-open", "Documents expiring / rejected", _docs_attention(db, company), "danger", "/account/documents"),
        ]
    else:
        to_receive = db.query(Order).filter(col == company.id, Order.status.in_((OrderStatus.DELIVERED, OrderStatus.INVOICED))).count()
        with_quotes = (db.query(RFQ.id).join(Quotation, Quotation.rfq_id == RFQ.id)
                       .filter(RFQ.buyer_company_id == company.id, RFQ.status == RFQStatus.OPEN,
                               Quotation.status == QuotationStatus.SUBMITTED).distinct().count())
        actions = [
            ("bi-tags", "RFQs with quotes to compare", with_quotes, "warning", "/buyer/rfqs?show=open"),
            ("bi-box-arrow-in-down", "Deliveries to confirm", to_receive, "primary", "/buyer/orders?show=delivered"),
            ("bi-geo-alt", "Shipments on the road", in_transit, "info", "/buyer/shipments"),
            ("bi-hourglass-split", "Awaiting seller confirmation",
             db.query(Order).filter(col == company.id, Order.status == OrderStatus.PENDING_CONFIRMATION).count(), "secondary",
             "/buyer/orders?show=pending_confirmation"),
            ("bi-folder2-open", "Documents expiring / rejected", _docs_attention(db, company), "danger", "/account/documents"),
        ]
    return {"months": [k[2:] for k in keys], "orders": [by.get(k, (0, 0))[0] for k in keys],
            "value": [round(by.get(k, (0, 0))[1], 2) for k in keys], "recent": recent, "actions": actions,
            "total_value": round(sum(v for _, v in by.values()), 2)}


def lab(db: Session, company: Company) -> dict:
    keys = month_keys(6)
    reqs = db.query(VerificationRequest).filter(VerificationRequest.lab_company_id == company.id,
                                                VerificationRequest.created_at >= _since(keys)).all()
    done = {k: [0, 0, []] for k in keys}
    for r in reqs:
        if r.completed_at and r.status in (VerificationStatus.COMPLETED, VerificationStatus.FAILED):
            k = r.completed_at.strftime("%Y-%m")
            if k in done:
                done[k][0 if r.status == VerificationStatus.COMPLETED else 1] += 1
                done[k][2].append((r.completed_at - r.created_at).total_seconds() / 86400)
    queue = (db.query(VerificationRequest)
             .filter(VerificationRequest.lab_company_id == company.id,
                     VerificationRequest.status.in_((VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED,
                                                     VerificationStatus.TESTING_IN_PROGRESS)))
             .order_by(VerificationRequest.is_priority.desc(), VerificationRequest.created_at).limit(6).all())
    return {"months": [k[2:] for k in keys],
            "series": [{"name": "Passed", "data": [done[k][0] for k in keys]}, {"name": "Failed", "data": [done[k][1] for k in keys]}],
            "turnaround": [{"name": "Avg days", "data": [round(sum(done[k][2]) / len(done[k][2]), 1) if done[k][2] else 0 for k in keys]}],
            "queue": queue, "docs": _docs_attention(db, company)}
