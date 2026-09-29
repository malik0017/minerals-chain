"""
app/services/spec_service.py
"""
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.md_quality import QualityParameter
from app.models.product import Product
from app.models.product_spec import ProductSpec
from app.services.master_data.batch_service import applicable_specs


class SpecError(ValueError):
    pass


def _dec(v) -> Decimal | None:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s == "":
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        raise SpecError(f"“{v}” is not a number.")


def catalog_rows(db: Session, product_master_id) -> list[dict]:
    if not product_master_id:
        return []
    rows = []
    for pid, s in applicable_specs(db, product_master_id).items():
        p = s.parameter
        rows.append({"parameter_id": pid, "parameter": (p.symbol or p.name_en) if p else "?",
                     "min": s.min_value, "max": s.max_value,
                     "unit": (s.uom.symbol or s.uom.code) if s.uom else ((p.default_uom.symbol or p.default_uom.code) if p and p.default_uom else None),
                     "test_method": (s.test_method.standard_ref or s.test_method.name_en) if s.test_method else None,
                     "sort": p.sort_order if p else 100})
    return sorted(rows, key=lambda r: (r["sort"], r["parameter"]))


def product_rows(db: Session, product: Product) -> list[dict]:
    if product.specs:
        return [{"parameter_id": s.parameter_id, "parameter": s.parameter, "min": s.min_value, "max": s.max_value,
                 "unit": s.unit, "test_method": s.test_method} for s in product.specs]
    return catalog_rows(db, product.product_master_id)


def parse_rows(form, prefix: str = "spec") -> list[dict]:
    names = form.getlist(f"{prefix}_param")
    mins, maxs = form.getlist(f"{prefix}_min"), form.getlist(f"{prefix}_max")
    units, methods = form.getlist(f"{prefix}_unit"), form.getlist(f"{prefix}_method")
    pids = form.getlist(f"{prefix}_pid")
    rows = []
    for i, name in enumerate(names):
        name = (name or "").strip()
        if not name:
            continue
        lo, hi = _dec(mins[i] if i < len(mins) else None), _dec(maxs[i] if i < len(maxs) else None)
        if lo is not None and hi is not None and lo > hi:
            raise SpecError(f"{name}: minimum is greater than maximum.")
        rows.append({"parameter": name[:80], "min": lo, "max": hi,
                     "unit": ((units[i] if i < len(units) else "") or "").strip()[:20] or None,
                     "test_method": ((methods[i] if i < len(methods) else "") or "").strip()[:80] or None,
                     "parameter_id": (pids[i] if i < len(pids) else "") or None})
    return rows


def save_product_specs(db: Session, product: Product, rows: list[dict]) -> None:
    for s in list(product.specs):
        db.delete(s)
    db.flush()
    known = {p.id.hex: p.id for p in db.query(QualityParameter.id)}
    for r in rows:
        pid = r.get("parameter_id")
        pid = known.get(str(pid).replace("-", "")) if pid else None
        db.add(ProductSpec(product_id=product.id, parameter_id=pid, parameter=r["parameter"], min_value=r["min"],
                           max_value=r["max"], unit=r["unit"], test_method=r["test_method"]))
    db.flush()
    db.refresh(product)


def judge(value: Decimal, lo, hi) -> bool:
    if lo is not None and value < Decimal(lo):
        return False
    if hi is not None and value > Decimal(hi):
        return False
    return True


def _key(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def match_score(required: list[dict], offered: list[dict]) -> int | None:
    if not required:
        return None
    by_name = {_key(o["parameter"]): o for o in offered}
    hits = 0
    for r in required:
        o = by_name.get(_key(r["parameter"]))
        if o is None:
            continue
        lo_ok = r["min"] is None or (o["min"] is not None and Decimal(o["min"]) >= Decimal(r["min"]))
        hi_ok = r["max"] is None or (o["max"] is not None and Decimal(o["max"]) <= Decimal(r["max"]))
        hits += 1 if (lo_ok and hi_ok) else 0
    return round(100 * hits / len(required))


def range_label(lo, hi, unit=None) -> str:
    def f(v):
        return f"{Decimal(v).normalize():f}"
    u = f" {unit}" if unit else ""
    if lo is not None and hi is not None:
        return f"{f(lo)}–{f(hi)}{u}"
    if lo is not None:
        return f"≥ {f(lo)}{u}"
    if hi is not None:
        return f"≤ {f(hi)}{u}"
    return "report"
