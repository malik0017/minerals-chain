"""
app/services/erp_export_service.py
"""
import csv
import hashlib
import io
import json
import zipfile
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyRole
from app.models.erp_export import ErpExportRun
from app.models.inventory import InventoryMovement
from app.models.order import Order, OrderStatus, SettlementFee, SettlementFeeStatus
from app.models.product import Product
from app.models.subscription import SubscriptionCharge
from app.models.user import User
from app.services import private_files

TARGETS = {"odoo": "Odoo (CSV import)", "sap_b1": "SAP Business One (Service Layer JSON)"}
DATASETS = {
    "partners": "Business partners",
    "products": "Items / products",
    "orders": "Sales orders",
    "invoices": "Invoices",
    "stock": "Stock movements",
}
PLATFORM_ONLY = {"invoices"}
VAT_CODE = {"odoo": "VAT 15%", "sap_b1": "S1"}
LIVE = (OrderStatus.CONFIRMED, OrderStatus.IN_TRANSIT, OrderStatus.DELIVERED, OrderStatus.INVOICED,
        OrderStatus.COMPLETED, OrderStatus.RESOLVED)


class ErpExportError(ValueError):
    pass


def _f(v) -> float:
    return float(v or 0)


def _pcode(c: Company) -> str:
    return f"{'S' if c.role == CompanyRole.SELLER else 'C' if c.role == CompanyRole.BUYER else 'L'}{c.cr_number}"


def _icode(p: Product) -> str:
    if p.product_master is not None:
        return p.product_master.code
    return f"MC-{str(p.id)[:8].upper()}"


def _range(q, col, start, end):
    if start:
        q = q.filter(col >= datetime.combine(start, time.min, tzinfo=timezone.utc))
    if end:
        q = q.filter(col < datetime.combine(end, time.max, tzinfo=timezone.utc))
    return q


def _orders(db, scope, start, end):
    q = db.query(Order).filter(Order.status.in_(LIVE))
    if scope:
        q = q.filter(Order.seller_company_id == scope.id)
    return _range(q, Order.confirmed_at, start, end).order_by(Order.confirmed_at).all()


def _partners(db, scope, start, end):
    if scope is None:
        return db.query(Company).order_by(Company.company_name).all()
    ids = {o.buyer_company_id for o in _orders(db, scope, start, end) if o.confirmed_at}
    return db.query(Company).filter(Company.id.in_(ids)).order_by(Company.company_name).all() if ids else []


def _products(db, scope):
    q = db.query(Product)
    if scope:
        q = q.filter(Product.seller_company_id == scope.id)
    return q.order_by(Product.mineral_type).all()


def _platform_invoices(db, start, end):
    fees = _range(db.query(SettlementFee).filter(SettlementFee.status != SettlementFeeStatus.WAIVED),
                  SettlementFee.created_at, start, end).all()
    subs = _range(db.query(SubscriptionCharge).filter(SubscriptionCharge.status.in_(["paid", "pending"])),
                  SubscriptionCharge.created_at, start, end).all()
    out = []
    for f in fees:
        out.append({"ref": f"FEE-{f.order.order_reference}-{f.party[0].upper()}", "partner": db.get(Company, f.paid_by_company_id),
                    "date": f.created_at.date(), "item": "SETTLEMENT-FEE", "desc": f"Settlement fee {f.party} · {f.order.order_reference}",
                    "net": f.amount_sar, "vat": f.vat_amount_sar, "total": f.total_sar, "paid": f.status == SettlementFeeStatus.PAID})
    for s in subs:
        out.append({"ref": s.reference, "partner": s.company, "date": s.created_at.date(), "item": f"SUB-{s.tier.upper()}",
                    "desc": f"Subscription {s.tier} {s.period_start} → {s.period_end or ''}", "net": s.amount_sar,
                    "vat": s.vat_amount_sar, "total": s.total_sar, "paid": s.status == "paid"})
    return sorted(out, key=lambda r: r["date"])


def _stock(db, scope, start, end):
    q = db.query(InventoryMovement)
    if scope:
        q = q.filter(InventoryMovement.company_id == scope.id)
    if start:
        q = q.filter(InventoryMovement.movement_date >= start)
    if end:
        q = q.filter(InventoryMovement.movement_date <= end)
    return q.order_by(InventoryMovement.movement_date).all()


def _csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _odoo(db, scope, start, end, datasets) -> dict[str, bytes]:
    files, counts = {}, {}
    if "partners" in datasets:
        rows = [{"id": f"mc_partner_{c.cr_number}", "name": c.company_name, "is_company": True,
                 "vat": c.vat_registration_number or "", "company_registry": c.cr_number, "email": c.contact_email,
                 "phone": c.contact_phone or "", "city": c.city or "", "country_id": "Saudi Arabia",
                 "customer_rank": 1 if c.role == CompanyRole.BUYER else 0,
                 "supplier_rank": 1 if c.role in (CompanyRole.SELLER, CompanyRole.LAB) else 0,
                 "comment": f"Minerals Chain {c.role.value} · {c.status.value}"} for c in _partners(db, scope, start, end)]
        files["res.partner.csv"], counts["partners"] = _csv(rows), len(rows)
    if "products" in datasets:
        rows, seen = [], set()
        for p in _products(db, scope):
            code = _icode(p) if scope is None else f"{_icode(p)}-{str(p.id)[:4]}"
            if code in seen:
                continue
            seen.add(code)
            rows.append({"id": f"mc_product_{code}", "name": f"{p.mineral_type}{' · ' + p.grade if p.grade else ''}",
                         "default_code": code, "type": "product", "uom_id": "Tons", "uom_po_id": "Tons",
                         "list_price": _f(p.price_value), "categ_id": "All / Minerals", "sale_ok": True, "purchase_ok": True})
        files["product.template.csv"], counts["products"] = _csv(rows), len(rows)
    if "orders" in datasets:
        rows = []
        for o in _orders(db, scope, start, end):
            rows.append({"id": f"mc_so_{o.order_reference}", "name": o.order_reference,
                         "partner_id/id": f"mc_partner_{o.buyer_company.cr_number}",
                         "date_order": o.confirmed_at.strftime("%Y-%m-%d %H:%M:%S") if o.confirmed_at else "",
                         "client_order_ref": o.rfq.rfq_reference or "", "incoterm": o.incoterm_code or "",
                         "order_line/name": o.rfq.mineral_type,
                         "order_line/product_id/id": f"mc_product_{_icode(o.quotation.product)}" if o.quotation and o.quotation.product else "",
                         "order_line/product_uom_qty": _f(o.quantity), "order_line/price_unit": _f(o.price_per_unit),
                         "order_line/tax_id": VAT_CODE["odoo"], "amount_untaxed": _f(o.subtotal_sar),
                         "amount_tax": _f(o.vat_amount_sar), "amount_total": _f(o.total_value_sar),
                         "x_mc_status": o.status.value, "x_mc_invoice": o.invoice_number or ""})
        files["sale.order.csv"], counts["orders"] = _csv(rows), len(rows)
    if "invoices" in datasets and scope is None:
        rows = [{"id": f"mc_inv_{r['ref']}", "move_type": "out_invoice", "name": r["ref"],
                 "partner_id/id": f"mc_partner_{r['partner'].cr_number}" if r["partner"] else "",
                 "invoice_date": r["date"].isoformat(), "invoice_line_ids/name": r["desc"],
                 "invoice_line_ids/product_id/id": f"mc_product_{r['item']}", "invoice_line_ids/quantity": 1,
                 "invoice_line_ids/price_unit": _f(r["net"]), "invoice_line_ids/tax_ids": VAT_CODE["odoo"],
                 "amount_tax": _f(r["vat"]), "amount_total": _f(r["total"]), "payment_state": "paid" if r["paid"] else "not_paid"}
                for r in _platform_invoices(db, start, end)]
        files["account.move.csv"], counts["invoices"] = _csv(rows), len(rows)
    if "stock" in datasets:
        rows = [{"id": f"mc_move_{m.reference}", "reference": m.reference, "date": m.movement_date.isoformat(),
                 "product_id/id": f"mc_product_{_icode(m.product)}" if m.product else "",
                 "product_uom_qty": abs(_f(m.quantity)), "product_uom": "Tons",
                 "location_id": (m.warehouse.code if m.warehouse else "Partners/Vendors") if m.quantity < 0 else "Partners/Vendors",
                 "location_dest_id": (m.warehouse.code if m.warehouse else "Partners/Customers") if m.quantity > 0 else "Partners/Customers",
                 "origin": m.order.order_reference if m.order else m.movement_type, "x_mc_type": m.movement_type,
                 "price_unit": _f(m.unit_cost_sar)} for m in _stock(db, scope, start, end)]
        files["stock.move.csv"], counts["stock"] = _csv(rows), len(rows)
    return files, counts


def _sap(db, scope, start, end, datasets):
    files, counts = {}, {}
    if "partners" in datasets:
        rows = [{"CardCode": _pcode(c), "CardName": c.company_name, "CardForeignName": c.company_name_ar,
                 "CardType": "cCustomer" if c.role == CompanyRole.BUYER else "cSupplier", "FederalTaxID": c.vat_registration_number,
                 "AdditionalID": c.cr_number, "EmailAddress": c.contact_email, "Phone1": c.contact_phone, "City": c.city,
                 "Country": "SA", "Currency": "SAR", "Valid": "tYES" if c.status.value == "approved" else "tNO"}
                for c in _partners(db, scope, start, end)]
        files["BusinessPartners.json"], counts["partners"] = _json({"value": rows}), len(rows)
    if "products" in datasets:
        rows, seen = [], set()
        for p in _products(db, scope):
            code = _icode(p)
            if code in seen:
                continue
            seen.add(code)
            rows.append({"ItemCode": code, "ItemName": f"{p.mineral_type}{' · ' + p.grade if p.grade else ''}"[:100],
                         "ForeignName": p.name_ar, "InventoryItem": "tYES", "SalesItem": "tYES", "PurchaseItem": "tYES",
                         "SalesUnit": "MT", "InventoryUOM": "MT", "PurchaseUnit": "MT",
                         "ItemPrices": [{"PriceList": 1, "Price": _f(p.price_value), "Currency": "SAR"}]})
        files["Items.json"], counts["products"] = _json({"value": rows}), len(rows)
    if "orders" in datasets:
        rows = []
        for o in _orders(db, scope, start, end):
            rows.append({"CardCode": _pcode(o.buyer_company), "NumAtCard": o.order_reference,
                         "DocDate": o.confirmed_at.date().isoformat() if o.confirmed_at else None,
                         "DocDueDate": (o.required_by or (o.confirmed_at.date() if o.confirmed_at else date.today())).isoformat(),
                         "DocCurrency": "SAR", "Comments": f"Minerals Chain {o.rfq.rfq_reference} · {o.status.value}",
                         "DocumentLines": [{"ItemCode": _icode(o.quotation.product) if o.quotation and o.quotation.product else "MC-GENERIC",
                                            "ItemDescription": o.rfq.mineral_type[:100], "Quantity": _f(o.quantity),
                                            "UnitPrice": _f(o.price_per_unit), "VatGroup": VAT_CODE["sap_b1"]}]})
        files["Orders.json"], counts["orders"] = _json({"value": rows}), len(rows)
    if "invoices" in datasets and scope is None:
        rows = [{"CardCode": _pcode(r["partner"]) if r["partner"] else None, "NumAtCard": r["ref"],
                 "DocDate": r["date"].isoformat(), "DocCurrency": "SAR", "Comments": r["desc"],
                 "DocumentLines": [{"ItemCode": r["item"], "Quantity": 1, "UnitPrice": _f(r["net"]), "VatGroup": VAT_CODE["sap_b1"]}],
                 "U_MC_Paid": "Y" if r["paid"] else "N"} for r in _platform_invoices(db, start, end)]
        files["Invoices.json"], counts["invoices"] = _json({"value": rows}), len(rows)
    if "stock" in datasets:
        entries, exits = [], []
        for m in _stock(db, scope, start, end):
            doc = {"DocDate": m.movement_date.isoformat(), "Reference2": m.reference,
                   "Comments": (m.order.order_reference if m.order else m.movement_type),
                   "DocumentLines": [{"ItemCode": _icode(m.product) if m.product else "MC-GENERIC", "Quantity": abs(_f(m.quantity)),
                                      "WarehouseCode": (m.warehouse.code if m.warehouse else "01")[:8],
                                      "UnitPrice": _f(m.unit_cost_sar)}]}
            (entries if m.quantity > 0 else exits).append(doc)
        files["InventoryGenEntries.json"] = _json({"value": entries})
        files["InventoryGenExits.json"] = _json({"value": exits})
        counts["stock"] = len(entries) + len(exits)
    return files, counts


def build(db: Session, *, target: str, datasets: list[str], start: date | None, end: date | None,
          scope: Company | None, user: User | None) -> ErpExportRun:
    if target not in TARGETS:
        raise ErpExportError("Choose Odoo or SAP Business One.")
    datasets = [d for d in datasets if d in DATASETS and not (scope and d in PLATFORM_ONLY)]
    if not datasets:
        raise ErpExportError("Choose at least one dataset.")
    if start and end and start > end:
        raise ErpExportError("Start date is after end date.")
    files, counts = (_odoo if target == "odoo" else _sap)(db, scope, start, end, datasets)
    manifest = {"system": "Minerals Chain", "target": target, "generated_at": datetime.now(timezone.utc).isoformat(),
                "scope": scope.company_name if scope else "platform", "period": [str(start or ""), str(end or "")],
                "counts": counts, "currency": "SAR", "vat_code": VAT_CODE[target],
                "notes": "Odoo: Settings → Import records per file (external IDs keep re-imports idempotent)."
                if target == "odoo" else "SAP B1: POST each file's value[] to the Service Layer endpoint of the same name."}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", _json(manifest))
        for name, data in files.items():
            z.writestr(name, data)
    data = buf.getvalue()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    stored = private_files.save_generated("erp_exports", f"{target}-{stamp}.zip", data, ext="zip")
    run = ErpExportRun(target=target, scope_company_id=scope.id if scope else None, datasets=datasets,
                       period_start=start, period_end=end, row_counts=counts, file_path=stored.path,
                       file_sha256=stored.sha256, file_size=len(data), status="success",
                       created_by_user_id=user.id if user else None)
    db.add(run)
    if user:
        db.flush()
        db.add(AuditLog(actor_user_id=user.id, action="erp_export", target_type="company", target_id=scope.id if scope else user.id,
                        details=f"{target} {','.join(datasets)} {start or ''}..{end or ''} {sum(counts.values())} rows"))
    db.commit()
    return run


def filename(run: ErpExportRun) -> str:
    return f"minerals-chain-{run.target}-{run.created_at:%Y%m%d-%H%M}.zip"
