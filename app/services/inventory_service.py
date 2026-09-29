"""
app/services/inventory_service.py
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.system_settings import get_setting
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.inventory import MOVEMENT_TYPES, InventoryMovement
from app.models.md_locations import Warehouse
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.services.reference_service import next_reference

Q = Decimal("0.001")


class InventoryError(ValueError):
    pass


def _qty(raw) -> Decimal:
    try:
        v = Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise InventoryError("Enter a valid quantity.")
    if v == 0:
        raise InventoryError("Quantity can't be zero.")
    return v.quantize(Q)


def _date(raw) -> date:
    if not raw:
        return date.today()
    try:
        d = date.fromisoformat(str(raw))
    except ValueError:
        raise InventoryError("Enter a valid date.")
    if d > date.today():
        raise InventoryError("Movement date can't be in the future.")
    return d


def warehouses_for(db: Session, company: Company) -> list[Warehouse]:
    return (db.query(Warehouse)
            .filter(Warehouse.is_active.is_(True), (Warehouse.company_id == company.id) | (Warehouse.company_id.is_(None)))
            .order_by(Warehouse.company_id.is_(None), Warehouse.name_en).all())


def _owned(db: Session, company: Company, product_id, warehouse_id) -> tuple[Product, Warehouse]:
    product = db.get(Product, uuid.UUID(str(product_id))) if product_id else None
    if product is None or product.seller_company_id != company.id:
        raise InventoryError("Choose one of your listings.")
    wh = db.get(Warehouse, uuid.UUID(str(warehouse_id))) if warehouse_id else None
    if wh is None or (wh.company_id not in (None, company.id)):
        raise InventoryError("Choose a warehouse.")
    return product, wh


def _add(db: Session, company: Company, user: User | None, *, product: Product, warehouse: Warehouse | None,
         movement_type: str, quantity: Decimal, movement_date: date, note: str | None = None, unit_cost=None,
         batch_id=None, order_id=None, transfer_group=None) -> InventoryMovement:
    m = InventoryMovement(reference=next_reference(db, "stock"), company_id=company.id,
                          warehouse_id=warehouse.id if warehouse else None, product_id=product.id,
                          product_master_id=product.product_master_id, batch_id=batch_id, order_id=order_id,
                          movement_type=movement_type, quantity=quantity, unit=product.quantity_unit or "MT",
                          unit_cost_sar=unit_cost, movement_date=movement_date, transfer_group=transfer_group,
                          note=(note or "").strip() or None, created_by_user_id=user.id if user else None)
    db.add(m)
    db.flush()
    return m


def on_hand(db: Session, company_id, product_id, warehouse_id=None) -> Decimal:
    q = db.query(func.coalesce(func.sum(InventoryMovement.quantity), 0)).filter(
        InventoryMovement.company_id == company_id, InventoryMovement.product_id == product_id)
    if warehouse_id:
        q = q.filter(InventoryMovement.warehouse_id == warehouse_id)
    return Decimal(q.scalar() or 0)


def _audit(db, user, m: InventoryMovement):
    if user:
        db.add(AuditLog(actor_user_id=user.id, action="stock_movement", target_type="company", target_id=m.company_id,
                        details=f"{m.reference} {m.movement_type} {m.quantity} {m.unit}"))


def record_receipt(db: Session, company: Company, user: User, form) -> InventoryMovement:
    product, wh = _owned(db, company, form.get("product_id"), form.get("warehouse_id"))
    qty = _qty(form.get("quantity"))
    if qty < 0:
        raise InventoryError("A receipt quantity must be positive.")
    cost = form.get("unit_cost_sar")
    try:
        cost = Decimal(cost) if cost not in (None, "") else None
    except InvalidOperation:
        raise InventoryError("Enter a valid unit cost.")
    m = _add(db, company, user, product=product, warehouse=wh, movement_type="receipt", quantity=qty,
             movement_date=_date(form.get("movement_date")), note=form.get("note"), unit_cost=cost,
             batch_id=_uuid(form.get("batch_id")))
    _audit(db, user, m)
    db.commit()
    return m


def record_adjustment(db: Session, company: Company, user: User, form) -> InventoryMovement:
    product, wh = _owned(db, company, form.get("product_id"), form.get("warehouse_id"))
    qty = _qty(form.get("quantity"))
    note = (form.get("note") or "").strip()
    if len(note) < 5:
        raise InventoryError("Explain the adjustment (e.g. stock count, spillage, moisture loss).")
    if qty < 0 and not get_setting(db, "allow_negative_stock") and on_hand(db, company.id, product.id, wh.id) + qty < 0:
        raise InventoryError("Adjustment would make stock negative.")
    m = _add(db, company, user, product=product, warehouse=wh, movement_type="adjustment", quantity=qty,
             movement_date=_date(form.get("movement_date")), note=note)
    _audit(db, user, m)
    db.commit()
    return m


def record_transfer(db: Session, company: Company, user: User, form) -> tuple[InventoryMovement, InventoryMovement]:
    product, src = _owned(db, company, form.get("product_id"), form.get("warehouse_id"))
    _, dst = _owned(db, company, form.get("product_id"), form.get("to_warehouse_id"))
    if src.id == dst.id:
        raise InventoryError("Choose two different warehouses.")
    qty = abs(_qty(form.get("quantity")))
    if not get_setting(db, "allow_negative_stock") and on_hand(db, company.id, product.id, src.id) < qty:
        raise InventoryError("Not enough stock in the source warehouse.")
    group, when = uuid.uuid4(), _date(form.get("movement_date"))
    out = _add(db, company, user, product=product, warehouse=src, movement_type="transfer_out", quantity=-qty,
               movement_date=when, note=form.get("note"), transfer_group=group)
    inn = _add(db, company, user, product=product, warehouse=dst, movement_type="transfer_in", quantity=qty,
               movement_date=when, note=form.get("note"), transfer_group=group)
    _audit(db, user, out)
    db.commit()
    return out, inn


def issue_for_order(db: Session, order: Order, user: User | None = None) -> InventoryMovement | None:
    if not get_setting(db, "inventory_auto_issue") or not order.product_id:
        return None
    if db.query(InventoryMovement).filter_by(order_id=order.id, movement_type="sale_issue").first():
        return None
    product = db.get(Product, order.product_id)
    qty = Decimal(order.quantity or order.rfq.quantity_value).quantize(Q)
    rows = (db.query(InventoryMovement.warehouse_id, func.sum(InventoryMovement.quantity))
            .filter(InventoryMovement.company_id == order.seller_company_id, InventoryMovement.product_id == product.id)
            .group_by(InventoryMovement.warehouse_id).order_by(func.sum(InventoryMovement.quantity).desc()).all())
    best_wh, best_qty = (rows[0][0], Decimal(rows[0][1])) if rows else (None, Decimal(0))
    if best_qty < qty and not get_setting(db, "allow_negative_stock"):
        raise InventoryError(f"Only {best_qty} {product.quantity_unit} in stock — record a receipt before shipping.")
    wh = db.get(Warehouse, best_wh) if best_wh else None
    return _add(db, order.seller_company, user, product=product, warehouse=wh, movement_type="sale_issue", quantity=-qty,
                movement_date=date.today(), note=f"Order {order.order_reference}", order_id=order.id)


def _uuid(v):
    try:
        return uuid.UUID(str(v)) if v else None
    except ValueError:
        return None


def reserved(db: Session, company_id) -> dict:
    rows = (db.query(Order.product_id, func.sum(Order.quantity))
            .filter(Order.seller_company_id == company_id, Order.product_id.isnot(None),
                    Order.status.in_([OrderStatus.PENDING_CONFIRMATION, OrderStatus.CONFIRMED]))
            .group_by(Order.product_id).all())
    return {pid: Decimal(q or 0) for pid, q in rows}


def balances(db: Session, company_id=None) -> list[dict]:
    q = (db.query(InventoryMovement.company_id, InventoryMovement.product_id, InventoryMovement.warehouse_id,
                  func.sum(InventoryMovement.quantity),
                  func.sum(case((InventoryMovement.quantity > 0, InventoryMovement.quantity * func.coalesce(InventoryMovement.unit_cost_sar, 0)), else_=0)),
                  func.sum(case((InventoryMovement.quantity > 0, InventoryMovement.quantity), else_=0)),
                  func.max(InventoryMovement.movement_date))
         .group_by(InventoryMovement.company_id, InventoryMovement.product_id, InventoryMovement.warehouse_id))
    if company_id:
        q = q.filter(InventoryMovement.company_id == company_id)
    rows = q.all()
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_({r[1] for r in rows if r[1]}))} if rows else {}
    whs = {w.id: w for w in db.query(Warehouse).filter(Warehouse.id.in_({r[2] for r in rows if r[2]}))} if rows else {}
    out = []
    for cid, pid, wid, qty, cost_total, in_qty, last in rows:
        qty = Decimal(qty or 0)
        avg = (Decimal(cost_total) / Decimal(in_qty)).quantize(Decimal("0.01")) if in_qty and cost_total else None
        out.append({"company_id": cid, "product": products.get(pid), "warehouse": whs.get(wid), "on_hand": qty,
                    "avg_cost": avg, "value": (qty * avg).quantize(Decimal("0.01")) if avg and qty > 0 else Decimal(0),
                    "last": last})
    return sorted(out, key=lambda r: (-(r["on_hand"])))


def summary(db: Session, company_id=None) -> dict:
    rows = balances(db, company_id)
    res = reserved(db, company_id) if company_id else {}
    by_product: dict = {}
    for r in rows:
        if r["product"] is None:
            continue
        key = r["product"].id
        e = by_product.setdefault(key, {"product": r["product"], "on_hand": Decimal(0), "value": Decimal(0)})
        e["on_hand"] += r["on_hand"]
        e["value"] += r["value"]
    for pid, e in by_product.items():
        e["reserved"] = res.get(pid, Decimal(0))
        e["available"] = e["on_hand"] - e["reserved"]
    since = date.today() - timedelta(days=84)
    mq = db.query(InventoryMovement).filter(InventoryMovement.movement_date >= since)
    if company_id:
        mq = mq.filter(InventoryMovement.company_id == company_id)
    weeks = [(since + timedelta(days=7 * i)) for i in range(13)]
    labels = [w.strftime("%m-%d") for w in weeks]
    ins, outs = [0.0] * 13, [0.0] * 13
    for m in mq:
        i = min((m.movement_date - since).days // 7, 12)
        if m.movement_type in ("transfer_in", "transfer_out"):
            continue
        if m.quantity > 0:
            ins[i] += float(m.quantity)
        else:
            outs[i] += float(-m.quantity)
    products = sorted(by_product.values(), key=lambda e: -e["on_hand"])
    return {
        "rows": rows, "products": products,
        "on_hand": sum((e["on_hand"] for e in products), Decimal(0)),
        "value": sum((e["value"] for e in products), Decimal(0)),
        "reserved": sum((e["reserved"] for e in products), Decimal(0)),
        "low": [e for e in products if e["available"] <= 0],
        "chart_products": [{"name": (e["product"].mineral_type + (f" · {e['product'].grade}" if e["product"].grade else ""))[:40],
                            "value": float(e["on_hand"])} for e in products[:12]],
        "weeks": labels, "ins": [round(v, 1) for v in ins], "outs": [round(v, 1) for v in outs],
    }


def ledger(db: Session, company_id=None, *, product_id=None, warehouse_id=None, movement_type="", start=None, end=None):
    q = db.query(InventoryMovement)
    if company_id:
        q = q.filter(InventoryMovement.company_id == company_id)
    if product_id:
        q = q.filter(InventoryMovement.product_id == product_id)
    if warehouse_id:
        q = q.filter(InventoryMovement.warehouse_id == warehouse_id)
    if movement_type in MOVEMENT_TYPES:
        q = q.filter(InventoryMovement.movement_type == movement_type)
    if start:
        q = q.filter(InventoryMovement.movement_date >= start)
    if end:
        q = q.filter(InventoryMovement.movement_date <= end)
    return q.order_by(InventoryMovement.movement_date.desc(), InventoryMovement.created_at.desc())


def create_warehouse(db: Session, company: Company, user: User, form) -> Warehouse:
    name = (form.get("name_en") or "").strip()
    if len(name) < 3:
        raise InventoryError("Enter the warehouse name.")
    n = db.query(func.count(Warehouse.id)).scalar() or 0
    wh = Warehouse(code=f"WH-{n + 1:04d}-{uuid.uuid4().hex[:4].upper()}", name_en=name,
                   name_ar=(form.get("name_ar") or "").strip() or None, company_id=company.id,
                   city=(form.get("city") or "").strip() or None,
                   national_address=(form.get("national_address") or "").strip()[:20] or None,
                   capacity_mt=Decimal(form.get("capacity_mt")) if form.get("capacity_mt") else None)
    db.add(wh)
    db.add(AuditLog(actor_user_id=user.id, action="warehouse_created", target_type="company", target_id=company.id,
                    details=name))
    db.commit()
    return wh
