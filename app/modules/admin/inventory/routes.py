"""
app/modules/admin/inventory/routes.py
"""
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.listing import paginate, qs
from app.core.permissions import require_admin
from app.core.portal_nav import build_portal_context
from app.core.templates import templates
from app.database.base import get_db
from app.models.company import Company
from app.models.inventory import MOVEMENT_TYPES
from app.models.user import User, UserRole
from app.services import inventory_service as inv

router = APIRouter(prefix="/admin/inventory", tags=["admin-inventory"])


@router.get("", name="admin_inventory")
def inventory(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("orders")),
              company: str = "", type: str = "", page: int = 1):
    s = inv.summary(db)
    by_company: dict = defaultdict(lambda: {"on_hand": Decimal(0), "value": Decimal(0), "lines": 0})
    for r in s["rows"]:
        e = by_company[r["company_id"]]
        e["on_hand"] += r["on_hand"]
        e["value"] += r["value"]
        e["lines"] += 1
    names = {c.id: c.company_name for c in db.query(Company).filter(Company.id.in_(list(by_company)))} if by_company else {}
    companies = sorted(({"id": k, "name": names.get(k, "?"), **v} for k, v in by_company.items()), key=lambda e: -e["on_hand"])
    by_mineral: dict = defaultdict(Decimal)
    for r in s["rows"]:
        if r["product"]:
            by_mineral[r["product"].mineral_type] += r["on_hand"]
    rows, total, page, pages = paginate(inv.ledger(db, inv._uuid(company), movement_type=type), page)
    ctx = build_portal_context(admin, UserRole.ADMIN, active_path="/admin/inventory")
    ctx.update({"s": s, "companies": companies, "moves": rows, "total": total, "page": page, "pages": pages,
                "qs": qs(company=company, type=type), "company": company, "type": type, "types": MOVEMENT_TYPES,
                "minerals": [{"name": k, "value": float(v)} for k, v in sorted(by_mineral.items(), key=lambda x: -x[1])][:12]})
    return templates.TemplateResponse(request, "admin/inventory.html", ctx)
