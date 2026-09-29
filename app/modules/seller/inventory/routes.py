"""
app/modules/seller/inventory/routes.py
"""
import csv
import io
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.core.forms import form_data
from app.core.listing import paginate, qs
from app.core.permissions import require_seller_company
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.batch import Batch
from app.models.inventory import MOVEMENT_TYPES
from app.models.product import Product
from app.models.user import User, UserRole
from app.services import inventory_service as inv

router = APIRouter(prefix="/seller/inventory", tags=["seller-inventory"])


def _back(msg=None, error=None, tab=""):
    q = f"?error={quote(error)}" if error else (f"?msg={quote(msg)}" if msg else "")
    return RedirectResponse(url="/seller/inventory" + q + (f"#{tab}" if tab else ""), status_code=303)


def _date(v):
    try:
        return date.fromisoformat(v) if v else None
    except ValueError:
        return None


@router.get("", name="seller_inventory")
def inventory(request: Request, db: Session = Depends(get_db), user: User = Depends(require_seller_company),
              product: str = "", warehouse: str = "", type: str = "", start: str = "", end: str = "", page: int = 1,
              msg: str | None = None, error: str | None = None):
    c = user.company
    summary = inv.summary(db, c.id)
    q = inv.ledger(db, c.id, product_id=inv._uuid(product), warehouse_id=inv._uuid(warehouse), movement_type=type,
                   start=_date(start), end=_date(end))
    rows, total, page, pages = paginate(q, page)
    ctx = build_portal_context(user, UserRole.SELLER, active_path="/seller/inventory")
    ctx.update({"s": summary, "moves": rows, "total": total, "page": page, "pages": pages,
                "qs": qs(product=product, warehouse=warehouse, type=type, start=start, end=end),
                "f": {"product": product, "warehouse": warehouse, "type": type, "start": start, "end": end},
                "products": db.query(Product).filter(Product.seller_company_id == c.id).order_by(Product.mineral_type).all(),
                "warehouses": inv.warehouses_for(db, c), "types": MOVEMENT_TYPES,
                "batches": db.query(Batch).filter(Batch.company_id == c.id).order_by(Batch.created_at.desc()).limit(200).all(),
                "today": date.today().isoformat(), "msg": msg, "error": error})
    return templates.TemplateResponse(request, "seller/inventory.html", ctx)


@router.post("/receipt", name="seller_inventory_receipt")
def receipt(form: FormData = Depends(form_data), db: Session = Depends(get_db), user: User = Depends(require_seller_company)):
    try:
        m = inv.record_receipt(db, user.company, user, form)
    except inv.InventoryError as exc:
        db.rollback()
        return _back(error=str(exc))
    return _back(msg=f"Receipt {m.reference} recorded.")


@router.post("/adjustment", name="seller_inventory_adjustment")
def adjustment(form: FormData = Depends(form_data), db: Session = Depends(get_db), user: User = Depends(require_seller_company)):
    try:
        m = inv.record_adjustment(db, user.company, user, form)
    except inv.InventoryError as exc:
        db.rollback()
        return _back(error=str(exc))
    return _back(msg=f"Adjustment {m.reference} recorded.")


@router.post("/transfer", name="seller_inventory_transfer")
def transfer(form: FormData = Depends(form_data), db: Session = Depends(get_db), user: User = Depends(require_seller_company)):
    try:
        out, _ = inv.record_transfer(db, user.company, user, form)
    except inv.InventoryError as exc:
        db.rollback()
        return _back(error=str(exc))
    return _back(msg=f"Transfer {out.reference} recorded.")


@router.post("/warehouses", name="seller_warehouse_create")
def warehouse_create(form: FormData = Depends(form_data), db: Session = Depends(get_db),
                     user: User = Depends(require_seller_company)):
    try:
        wh = inv.create_warehouse(db, user.company, user, form)
    except (inv.InventoryError, ArithmeticError, ValueError) as exc:
        db.rollback()
        return _back(error=str(exc) or "Invalid capacity.")
    return _back(msg=f"Warehouse {wh.name_en} added.")


@router.get("/export.csv", name="seller_inventory_csv")
def export(db: Session = Depends(get_db), user: User = Depends(require_seller_company)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Reference", "Date", "Type", "Listing", "Warehouse", "Quantity", "Unit", "Unit cost SAR", "Order", "Note"])
    for m in inv.ledger(db, user.company_id).limit(20000):
        w.writerow([m.reference, m.movement_date, m.type_label, m.product.mineral_type if m.product else "",
                    m.warehouse.name_en if m.warehouse else "", m.quantity, m.unit, m.unit_cost_sar or "",
                    m.order.order_reference if m.order else "", m.note or ""])
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="stock-ledger.csv"'})
