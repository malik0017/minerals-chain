"""
app/modules/admin/shipments/routes.py
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.permissions import require_admin
from app.database.base import get_db
from app.models.user import User, UserRole
from app.modules.shared import shipment_views as v

router = APIRouter(prefix="/admin/shipments", tags=["admin-shipments"])
BASE = "/admin/shipments"


@router.get("", name="admin_shipments")
def index(request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin("orders")),
          status: str = "", q: str = "", page: int = 1):
    return v.page(request, db, admin, UserRole.ADMIN, BASE, status, q, page)


@router.get("/export.csv", name="admin_shipments_csv")
def export(db: Session = Depends(get_db), admin: User = Depends(require_admin("orders")), status: str = "", q: str = ""):
    return v.export_csv(db, admin, UserRole.ADMIN, status, q)
