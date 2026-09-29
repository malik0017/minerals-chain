"""
app/services/analytics_service.py
"""
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.models.certification import Certification, CertificationStatus, CertificationType
from app.models.company import ApprovalStatus, Company, CompanyRole
from app.models.dispute import Dispute, DisputeStatus
from app.models.order import Order, OrderStatus, SettlementFee, SettlementFeeStatus
from app.models.product import Product, ProductStatus
from app.models.rfq import RFQ, RFQStatus
from app.models.subscription import SubscriptionCharge
from app.models.user import User
from app.models.verification import VerificationRequest, VerificationStatus

LIVE_ORDER = (OrderStatus.CONFIRMED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED, OrderStatus.INVOICED,
              OrderStatus.COMPLETED, OrderStatus.RESOLVED, OrderStatus.DISPUTED)


def _f(v) -> float:
    return float(v or 0)


def month_keys(n: int = 12, end: date | None = None) -> list[str]:
    end = end or date.today()
    y, m = end.year, end.month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def _by_month(rows, keys) -> list[float]:
    d = {k: 0.0 for k in keys}
    for k, v in rows:
        if k in d:
            d[k] += _f(v)
    return [round(d[k], 2) for k in keys]


def _month(col):
    return func.to_char(col, "YYYY-MM")



def dashboard(db: Session) -> dict:
    keys = month_keys(12)
    since = datetime.strptime(keys[0] + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)

    gmv = db.scalar(func.coalesce(func.sum(Order.total_value_sar), 0).select().where(Order.status.in_(LIVE_ORDER)))
    orders_total = db.scalar(func.count(Order.id).select())
    fees_paid = db.scalar(func.coalesce(func.sum(SettlementFee.amount_sar), 0).select()
                          .where(SettlementFee.status == SettlementFeeStatus.PAID))
    subs_paid = db.scalar(func.coalesce(func.sum(SubscriptionCharge.amount_sar), 0).select()
                          .where(SubscriptionCharge.status == "paid"))
    kpis = {
        "gmv": _f(gmv), "orders": orders_total or 0,
        "companies": db.scalar(func.count(Company.id).select().where(Company.status == ApprovalStatus.APPROVED)) or 0,
        "pending": db.scalar(func.count(Company.id).select().where(Company.status == ApprovalStatus.PENDING)) or 0,
        "users": db.scalar(func.count(User.id).select().where(User.is_active.is_(True))) or 0,
        "listings": db.scalar(func.count(Product.id).select().where(Product.status == ProductStatus.VERIFIED)) or 0,
        "open_rfqs": db.scalar(func.count(RFQ.id).select().where(RFQ.status == RFQStatus.OPEN)) or 0,
        "open_disputes": db.scalar(func.count(Dispute.id).select().where(Dispute.status.in_(
            [DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW, DisputeStatus.AWAITING_INFO]))) or 0,
        "lab_queue": db.scalar(func.count(VerificationRequest.id).select().where(VerificationRequest.status.in_(
            [VerificationStatus.REQUESTED, VerificationStatus.SAMPLE_SCHEDULED, VerificationStatus.TESTING_IN_PROGRESS]))) or 0,
        "passports_pending": db.scalar(func.count(Certification.id).select().where(
            Certification.cert_type == CertificationType.MINERAL_PASSPORT,
            Certification.status == CertificationStatus.PENDING)) or 0,
        "revenue": _f(fees_paid) + _f(subs_paid),
    }

    order_status = [{"name": s.value.replace("_", " ").capitalize(), "value": n}
                    for s, n in db.query(Order.status, func.count()).group_by(Order.status).all() if n]

    monthly_orders = db.query(_month(Order.created_at), func.count()).filter(Order.created_at >= since) \
        .group_by(_month(Order.created_at)).all()
    monthly_gmv = db.query(_month(Order.created_at), func.sum(Order.total_value_sar)) \
        .filter(Order.created_at >= since, Order.status.in_(LIVE_ORDER)).group_by(_month(Order.created_at)).all()

    roles = [r for r in CompanyRole if r != getattr(CompanyRole, "ADMIN", None)]
    statuses = list(ApprovalStatus)
    grid = {(r, s): n for r, s, n in db.query(Company.role, Company.status, func.count())
            .group_by(Company.role, Company.status).all()}
    companies = {"roles": [r.value.capitalize() for r in roles],
                 "series": [{"name": s.value.capitalize(), "data": [grid.get((r, s), 0) for r in roles]} for s in statuses]}

    listings = [{"name": s.value.replace("_", " ").capitalize(), "value": n}
                for s, n in db.query(Product.status, func.count()).group_by(Product.status).all() if n]

    fee_status = [{"name": s.value.capitalize(), "value": round(_f(v), 2)}
                  for s, v in db.query(SettlementFee.status, func.sum(SettlementFee.amount_sar))
                  .group_by(SettlementFee.status).all() if v]

    reg = {}
    for role, m, n in db.query(Company.role, _month(Company.created_at), func.count()) \
            .filter(Company.created_at >= since).group_by(Company.role, _month(Company.created_at)).all():
        reg.setdefault(role.value, []).append((m, n))
    registrations = [{"name": r.value.capitalize(), "data": _by_month(reg.get(r.value, []), keys)} for r in roles]

    return {"kpis": kpis, "months": keys, "order_status": order_status,
            "monthly_orders": _by_month(monthly_orders, keys), "monthly_gmv": _by_month(monthly_gmv, keys),
            "companies": companies, "listings": listings, "fee_status": fee_status, "registrations": registrations}


def security_score(checklist: list[dict]) -> int:
    weights = {"ok": 1.0, "info": 0.75, "warn": 0.4, "fail": 0.0}
    if not checklist:
        return 0
    return round(100 * sum(weights[i["level"]] for i in checklist) / len(checklist))


def parse_range(start: str, end: str) -> tuple[date, date]:
    today = date.today()
    try:
        d_end = date.fromisoformat(end) if end else today
    except ValueError:
        d_end = today
    try:
        d_start = date.fromisoformat(start) if start else (d_end.replace(day=1) - timedelta(days=330)).replace(day=1)
    except ValueError:
        d_start = (d_end - timedelta(days=365)).replace(day=1)
    if d_start > d_end:
        d_start, d_end = d_end, d_start
    return d_start, d_end


def _months_between(a: date, b: date) -> list[str]:
    out, y, m = [], a.year, a.month
    while (y, m) <= (b.year, b.month):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def report(db: Session, start: date, end: date) -> dict:
    t0 = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    t1 = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    keys = _months_between(start, end)

    def in_range(col):
        return and_(col >= t0, col < t1)

    # --- revenue streams (platform income, net of VAT) ---
    fees = db.query(_month(SettlementFee.created_at), func.sum(SettlementFee.amount_sar)) \
        .filter(in_range(SettlementFee.created_at), SettlementFee.status.in_([SettlementFeeStatus.PAID, SettlementFeeStatus.PENDING])) \
        .group_by(_month(SettlementFee.created_at)).all()
    subs = db.query(_month(SubscriptionCharge.created_at), func.sum(SubscriptionCharge.amount_sar)) \
        .filter(in_range(SubscriptionCharge.created_at), SubscriptionCharge.status.in_(["paid", "pending"])) \
        .group_by(_month(SubscriptionCharge.created_at)).all()
    labs = db.query(_month(VerificationRequest.created_at), func.sum(VerificationRequest.fee_sar)) \
        .filter(in_range(VerificationRequest.created_at)).group_by(_month(VerificationRequest.created_at)).all()
    passports = db.query(_month(Certification.created_at), func.sum(Certification.fee_sar)) \
        .filter(in_range(Certification.created_at), Certification.cert_type == CertificationType.MINERAL_PASSPORT,
                Certification.status != CertificationStatus.REJECTED).group_by(_month(Certification.created_at)).all()
    streams = OrderedDict([("Settlement fees", _by_month(fees, keys)), ("Subscriptions", _by_month(subs, keys)),
                           ("Lab verification fees", _by_month(labs, keys)), ("Passport fees", _by_month(passports, keys))])
    stream_totals = {k: round(sum(v), 2) for k, v in streams.items()}

    fee_state = {s.value: round(_f(v), 2) for s, v in db.query(SettlementFee.status, func.sum(SettlementFee.amount_sar))
                 .filter(in_range(SettlementFee.created_at)).group_by(SettlementFee.status).all()}

    # --- orders: normal vs dispute outcome ---
    orders_q = db.query(Order).filter(in_range(Order.created_at))
    normal = orders_q.filter(Order.status == OrderStatus.COMPLETED, Order.completed_via_dispute.is_(False)).count()
    via_dispute = orders_q.filter(Order.completed_via_dispute.is_(True)).count()
    in_progress = orders_q.filter(Order.status.in_([OrderStatus.PENDING_CONFIRMATION, OrderStatus.CONFIRMED,
                                                    OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED,
                                                    OrderStatus.INVOICED, OrderStatus.DISPUTED])).count()
    cancelled = orders_q.filter(Order.status == OrderStatus.CANCELLED).count()
    gmv_month = db.query(_month(Order.created_at), func.sum(Order.total_value_sar)) \
        .filter(in_range(Order.created_at), Order.status.in_(LIVE_ORDER)).group_by(_month(Order.created_at)).all()
    orders_month = db.query(_month(Order.created_at), func.count()) \
        .filter(in_range(Order.created_at)).group_by(_month(Order.created_at)).all()

    # --- disputes ---
    d_rows = db.query(Dispute.status, Dispute.ruling, func.count()).filter(in_range(Dispute.created_at)) \
        .group_by(Dispute.status, Dispute.ruling).all()
    disputes = {"For buyer": 0, "For seller": 0, "Withdrawn": 0, "Open": 0}
    for st, ruling, n in d_rows:
        if st == DisputeStatus.RESOLVED:
            disputes["For buyer" if ruling and ruling.value == "buyer" else "For seller"] += n
        elif st == DisputeStatus.WITHDRAWN:
            disputes["Withdrawn"] += n
        else:
            disputes["Open"] += n
    by_category = [{"name": c.replace("_", " ").capitalize(), "value": n} for c, n in
                   db.query(Dispute.category, func.count()).filter(in_range(Dispute.created_at)).group_by(Dispute.category).all()]

    # --- labs ---
    lab_rows = db.query(Company.company_name, VerificationRequest.status, func.count()) \
        .join(Company, Company.id == VerificationRequest.lab_company_id) \
        .filter(in_range(VerificationRequest.created_at)) \
        .group_by(Company.company_name, VerificationRequest.status).all()
    lab = {}
    for name, st, n in lab_rows:
        e = lab.setdefault(name, {"passed": 0, "failed": 0, "active": 0})
        if st == VerificationStatus.COMPLETED:
            e["passed"] += n
        elif st == VerificationStatus.FAILED:
            e["failed"] += n
        else:
            e["active"] += n
    labs_table = sorted([{"lab": k, **v, "rate": round(100 * v["passed"] / (v["passed"] + v["failed"]))
                          if (v["passed"] + v["failed"]) else None} for k, v in lab.items()],
                        key=lambda r: -(r["passed"] + r["failed"] + r["active"]))

    # --- top minerals by GMV ---
    top = db.query(RFQ.mineral_type, func.count(Order.id), func.sum(Order.total_value_sar)) \
        .join(RFQ, RFQ.id == Order.rfq_id).filter(in_range(Order.created_at), Order.status.in_(LIVE_ORDER)) \
        .group_by(RFQ.mineral_type).order_by(func.sum(Order.total_value_sar).desc()).limit(10).all()

    return {
        "start": start, "end": end, "months": keys, "streams": streams, "stream_totals": stream_totals,
        "revenue_total": round(sum(stream_totals.values()), 2), "fee_state": fee_state,
        "orders": {"normal": normal, "via_dispute": via_dispute, "in_progress": in_progress, "cancelled": cancelled,
                   "gmv_month": _by_month(gmv_month, keys), "count_month": _by_month(orders_month, keys),
                   "gmv": round(sum(_by_month(gmv_month, keys)), 2)},
        "disputes": disputes, "dispute_categories": by_category, "labs": labs_table,
        "top_minerals": [{"mineral": m, "orders": n, "gmv": round(_f(v), 2)} for m, n, v in top],
    }


def report_csv_rows(r: dict) -> list[list]:
    rows = [["Minerals Chain platform report", f"{r['start']} to {r['end']}"], [],
            ["Revenue stream (SAR, net of VAT)"] + r["months"] + ["Total"]]
    for name, vals in r["streams"].items():
        rows.append([name] + vals + [r["stream_totals"][name]])
    rows += [[], ["Orders"] + r["months"], ["Order count"] + r["orders"]["count_month"],
             ["GMV incl. VAT"] + r["orders"]["gmv_month"], [],
             ["Order outcome", "Count"], ["Completed normally", r["orders"]["normal"]],
             ["Completed via dispute resolution", r["orders"]["via_dispute"]],
             ["In progress", r["orders"]["in_progress"]], ["Cancelled", r["orders"]["cancelled"]], [],
             ["Dispute outcome", "Count"]] + [[k, v] for k, v in r["disputes"].items()]
    rows += [[], ["Lab", "Passed", "Failed", "Active", "Pass rate %"]] + \
            [[l["lab"], l["passed"], l["failed"], l["active"], l["rate"] if l["rate"] is not None else ""] for l in r["labs"]]
    rows += [[], ["Mineral", "Orders", "GMV incl. VAT"]] + [[t["mineral"], t["orders"], t["gmv"]] for t in r["top_minerals"]]
    return rows
